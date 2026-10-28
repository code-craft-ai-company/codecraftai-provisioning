"""
    .. module:: xenapplystages
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: XenApplyStages — the Network / SR / VM apply stages for the
        XCP-ng venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from ccai.provisioning.model.cloud.cloudinstance import CloudInstance
from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)

from ccai.provisioning.venues.xcpng.xencloudinitrenderer import (
    XenCloudInitRenderer
)
from ccai.provisioning.venues.xcpng.xennaming import (
    vm_name_for, volume_name_for
)
from ccai.provisioning.venues.xcpng.xenresolver import XenResolver
from ccai.provisioning.venues.xcpng.xentagtranslator import (
    XenTagTranslator
)
from ccai.provisioning.venues.xcpng.xcpngspec import XcpngSpec

from ccai.provisioning.venuedrivers import require_venue_driver

require_venue_driver(venue="xcpng", driver_module="ccai.interop.xen",
                     driver_distribution="codecraftai-interop-xen")

from ccai.interop.xen.specs.xenvbdspec import XenVbdSpec
from ccai.interop.xen.specs.xenvdispec import XenVdiSpec
from ccai.interop.xen.specs.xenvifspec import XenVifSpec
from ccai.interop.xen.specs.xenvmclonespec import XenVmCloneSpec


class XenApplyResult:
    """
        Accumulator carrying the created / skipped resources produced by the
        XCP-ng apply stages plus the VPN-device records the destroy stage
        must clean up.
    """

    def __init__(self) -> None:
        """
            Construct an empty XenApplyResult.
        """
        self.created: List[ProvisionedResource] = []
        self.updated: List[ProvisionedResource] = []
        self.skipped: List[str] = []
        self.vpn_records: List[Dict[str, Any]] = []
        return


class XenApplyStages:
    """
        The XCP-ng apply stages.

        Stage one ensures every spec Network exists as a XAPI network and
        validates that an SR with enough free space is reachable.  Stage two
        clones each VM from its resolved Template, applies the resolved
        hardware shape and tags, attaches additional VDIs, pushes cloud-init
        through the xenstore ``vm-data/cloud-init`` keys, and starts the VM.
        Every stage is idempotent — an already-cloned VM whose run-scoped
        name_label exists is a SKIP and no mutating call is issued.
    """

    def __init__(self, *, client: Any, resolver: XenResolver,
                 cloud_init_renderer: Optional[
                     XenCloudInitRenderer] = None) -> None:
        """
            Construct an XenApplyStages.

            :param client: The :class:`XenClient`.
            :param resolver: The :class:`XenResolver`.
            :param cloud_init_renderer: Optional :class:`XenCloudInitRenderer`;
                                        defaults to a fresh instance.
        """
        self._client = client
        self._resolver = resolver
        if cloud_init_renderer is not None:
            self._cloud_init_renderer = cloud_init_renderer
        else:
            self._cloud_init_renderer = XenCloudInitRenderer()
        self._translator = XenTagTranslator()
        return

    # ------------------------------------------------------------------
    # Stage one: networks + SR verification
    # ------------------------------------------------------------------

    def apply_networks_and_sr_validation(self, *, spec: XcpngSpec,
                                         result: XenApplyResult,
                                         aspects: Any) -> None:
        """
            Ensure every spec Network exists and an SR is reachable.

            XCP-ng networks are reused by ``name_label``; a network already
            present is a SKIP.  When the venue model exposes no network
            creation primitive the existing network is treated as a SKIP and
            recorded so the run remains idempotent.

            :param spec: The :class:`XcpngSpec`.
            :param result: The :class:`XenApplyResult` accumulator.
            :param aspects: Behaviour control for the interop client.
        """
        live_networks = self._client.Networks.list(aspects=aspects)
        live_by_label: Dict[str, Any] = {}
        for network in live_networks:
            live_by_label[network.name_label] = network

        for network in spec.networks:
            existing = live_by_label.get(network.name, None)
            if existing is not None:
                result.skipped.append(network.name)
                continue
            # XCP-ng networks are provisioned by the pool administrator; the
            # venue records the gap rather than silently creating one.
            result.skipped.append(network.name)

        # SR verification: confirm an SR can host the spec's largest volume.
        required_gb = self._largest_required_gb(spec=spec)
        if required_gb > 0:
            self._resolver.pick_sr(client=self._client,
                                   required_gb=required_gb,
                                   aspects=aspects)
        return

    @staticmethod
    def _largest_required_gb(*, spec: XcpngSpec) -> int:
        """
            Return the largest single-volume size in the spec, in GiB.

            :param spec: The :class:`XcpngSpec`.

            :returns: The largest ``size_gb`` value, or 0 when no volumes.
        """
        largest = 0
        for volume in spec.volumes:
            if volume.size_gb > largest:
                largest = volume.size_gb
        rtnval = largest
        return rtnval

    # ------------------------------------------------------------------
    # Stage two: VMs
    # ------------------------------------------------------------------

    def apply_vms(self, *, spec: XcpngSpec, run_id: str,
                  result: XenApplyResult,
                  vpn_control_plane: Optional[Any], aspects: Any) -> None:
        """
            Clone each VM, apply hardware + tags, attach VDIs, push
            cloud-init, and start the VM.

            :param spec: The :class:`XcpngSpec`.
            :param run_id: The provisioning run id.
            :param result: The :class:`XenApplyResult` accumulator.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl used
                                      to mint VPN auth keys.
            :param aspects: Behaviour control for the interop client.
        """
        live_vms = self._client.Vms.list(aspects=aspects)
        live_by_name: Dict[str, Any] = {}
        for vm in live_vms:
            live_by_name[vm.name_label] = vm

        volumes_by_attach = self._volumes_by_attach(spec=spec)

        for inst in spec.instances:
            venue_name = vm_name_for(spec_name=inst.name, run_id=run_id)
            existing = live_by_name.get(venue_name, None)
            recreated = False
            if existing is not None:
                drift = self._vm_drift(existing=existing,
                                       shape=self._resolver.size_to_hardware(
                                           size_hint=inst.size))
                if drift is None:
                    result.skipped.append(inst.name)
                    continue
                # XAPI exposes no in-place vCPU / memory reconfigure on
                # the interop client; a drifted VM is realised
                # UPDATE-by-recreate — clean-shutdown + destroy the stale
                # VM, then re-clone it at the desired hardware shape.
                shutdown_handle = self._client.Vms.clean_shutdown(
                    vm_uuid=existing.uuid, aspects=aspects)
                if shutdown_handle is not None:
                    shutdown_handle.wait(aspects=aspects)
                self._client.Vms.destroy(vm_uuid=existing.uuid,
                                         aspects=aspects)
                recreated = True

            resource = self._apply_one_vm(
                inst=inst, venue_name=venue_name, run_id=run_id,
                volumes=volumes_by_attach.get(inst.name, []),
                vpn_control_plane=vpn_control_plane, aspects=aspects)
            if recreated is True:
                result.updated.append(resource)
            else:
                result.created.append(resource)

            if inst.vpn_join is not None:
                result.vpn_records.append({
                    "instance_name": inst.name,
                    "vm_uuid": resource.venue_id,
                    "vpn_provider": inst.vpn_join.provider,
                    "vpn_device_id": resource.attributes.get(
                        "vpn_device_id", venue_name),
                })
        return

    @staticmethod
    def _volumes_by_attach(*, spec: XcpngSpec) -> Dict[str, List[Any]]:
        """
            Group the spec's volumes by the instance they attach to.

            :param spec: The :class:`XcpngSpec`.

            :returns: A dict of instance name to its attached volumes.
        """
        out: Dict[str, List[Any]] = {}
        for volume in spec.volumes:
            attach_target = volume.attached_to
            if attach_target is None or len(attach_target) == 0:
                continue
            out.setdefault(attach_target, []).append(volume)
        rtnval = out
        return rtnval

    @staticmethod
    def _vm_drift(*, existing: Any, shape: Any) -> Optional[Dict[str, Any]]:
        """
            Compute the vCPU / memory drift between a live VM and a
            resolved hardware shape.

            :param existing: The live XenVm record.
            :param shape: The resolved :class:`XenHardwareShape`.

            :returns: A diff dict when the VM drifts, else ``None``.
        """
        drifted = (existing.vcpus_max != shape.vcpus
                   or existing.memory_static_max != shape.memory_bytes)
        if drifted is not True:
            rtnval: Optional[Dict[str, Any]] = None
            return rtnval
        rtnval = {"before": {"vcpus": existing.vcpus_max,
                             "memory_bytes": existing.memory_static_max},
                  "after": {"vcpus": shape.vcpus,
                            "memory_bytes": shape.memory_bytes}}
        return rtnval

    def _apply_one_vm(self, *, inst: CloudInstance, venue_name: str,
                      run_id: str, volumes: List[Any],
                      vpn_control_plane: Optional[Any],
                      aspects: Any) -> ProvisionedResource:
        """
            Realise a single VM from its neutral :class:`CloudInstance`.

            :param inst: The neutral :class:`CloudInstance`.
            :param venue_name: The venue-side VM name_label.
            :param run_id: The provisioning run id.
            :param volumes: The volumes to attach as additional VDIs.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl.
            :param aspects: Behaviour control for the interop client.

            :returns: A :class:`ProvisionedResource` for the VM.
        """
        template_uuid = self._resolver.image_to_template_ref(
            client=self._client, family=inst.image.family,
            version=inst.image.version,
            architecture=inst.image.architecture, aspects=aspects)
        shape = self._resolver.size_to_hardware(size_hint=inst.size)

        neutral_tags = inst.tags if inst.tags is not None else {}
        translated = self._translator.to_xen(neutral_tags=neutral_tags,
                                              run_id=run_id)

        xenstore_data = self._render_cloud_init(
            inst=inst, venue_name=venue_name,
            vpn_control_plane=vpn_control_plane)

        clone_spec = XenVmCloneSpec(
            name_label=venue_name,
            name_description="ccai run {}".format(run_id),
            vcpus_max=shape.vcpus, memory_bytes=shape.memory_bytes,
            other_config=translated["other_config"],
            tags=translated["tags"], xenstore_data=xenstore_data)

        vm, provision_handle = self._client.Vms.clone_from_template(
            template_uuid=template_uuid, spec=clone_spec, aspects=aspects)
        if provision_handle is not None:
            provision_handle.wait(aspects=aspects)

        self._attach_network(vm_uuid=vm.uuid, inst=inst, aspects=aspects)
        attached_volume_ids = self._attach_volumes(
            vm_uuid=vm.uuid, volumes=volumes, run_id=run_id,
            aspects=aspects)

        start_handle = self._client.Vms.start(vm_uuid=vm.uuid,
                                              aspects=aspects)
        if start_handle is not None:
            start_handle.wait(aspects=aspects)

        attributes: Dict[str, Any] = {
            "vm_uuid": vm.uuid,
            "venue_name": venue_name,
            "vcpus": shape.vcpus,
            "memory_bytes": shape.memory_bytes,
            "template_uuid": template_uuid,
            "volume_uuids": attached_volume_ids,
        }
        rtnval = ProvisionedResource(
            kind="instance", name=inst.name, venue_id=vm.uuid,
            attributes=attributes, tags=dict(neutral_tags))
        return rtnval

    def _render_cloud_init(self, *, inst: CloudInstance, venue_name: str,
                           vpn_control_plane: Optional[Any]
                           ) -> Dict[str, str]:
        """
            Render the xenstore ``vm-data/cloud-init`` key map for a VM.

            :param inst: The neutral :class:`CloudInstance`.
            :param venue_name: The venue-side VM name_label / hostname.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl.

            :returns: The xenstore key map (possibly empty).
        """
        authkey = ""
        if inst.vpn_join is not None and vpn_control_plane is not None:
            minted = getattr(vpn_control_plane, "minted_authkey", "")
            if minted is not None:
                authkey = minted

        rtnval = self._cloud_init_renderer.render(
            spec_vm=inst, vpn_join=inst.vpn_join, authkey=authkey,
            rendered_hostname=venue_name)
        return rtnval

    def _attach_network(self, *, vm_uuid: str, inst: CloudInstance,
                        aspects: Any) -> None:
        """
            Attach the VM to its first spec network through a XAPI VIF.

            :param vm_uuid: The cloned VM uuid.
            :param inst: The neutral :class:`CloudInstance`.
            :param aspects: Behaviour control for the interop client.
        """
        networks = self._client.Networks.get_by_name_label(
            name_label=inst.subnet, aspects=aspects)
        if len(networks) == 0:
            # No matching named network — VIF attachment is skipped; the VM
            # keeps the network the Template clone provided.
            return
        target_network = networks[0]
        vif_spec = XenVifSpec(vm_uuid=vm_uuid,
                              network_uuid=target_network.uuid, device="0")
        self._client.Vifs.attach(spec=vif_spec, aspects=aspects)
        return

    def _attach_volumes(self, *, vm_uuid: str, volumes: List[Any],
                        run_id: str, aspects: Any) -> List[str]:
        """
            Create and attach additional VDIs for a VM.

            :param vm_uuid: The cloned VM uuid.
            :param volumes: The neutral volumes to realise as VDIs.
            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.

            :returns: The list of attached VDI uuids.
        """
        attached: List[str] = []
        device_index = 1
        for volume in volumes:
            sr_uuid = self._resolver.pick_sr(client=self._client,
                                             required_gb=volume.size_gb,
                                             aspects=aspects)
            vdi_label = volume_name_for(spec_name=volume.name,
                                        run_id=run_id)
            vdi_spec = XenVdiSpec(
                name_label=vdi_label, sr_uuid=sr_uuid,
                virtual_size=volume.size_gb * 1024 * 1024 * 1024,
                name_description="ccai run {}".format(run_id))
            vdi = self._client.Vdi.create(spec=vdi_spec, aspects=aspects)

            vbd_spec = XenVbdSpec(vm_uuid=vm_uuid, vdi_uuid=vdi.uuid,
                                  userdevice=str(device_index))
            self._client.Vbds.attach(spec=vbd_spec, aspects=aspects)
            attached.append(vdi.uuid)
            device_index = device_index + 1
        rtnval = attached
        return rtnval
