"""
    .. module:: pveapplystages
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: PveApplyStages — the networking, firewall, and VM apply
               stages for the Proxmox VE venue provisioner.

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
from ccai.provisioning.venues.proxmox.pvecloudinitrenderer import (
    PveCloudInitRenderer
)
from ccai.provisioning.venues.proxmox.pvenaming import (
    OWNER_TAG, has_run_id_tag, run_id_tag, vm_name_for
)
from ccai.provisioning.venues.proxmox.pveresolver import PveResolver
from ccai.provisioning.venues.proxmox.pvetagtranslator import (
    PveTagTranslator
)
from ccai.provisioning.venues.proxmox.proxmoxspec import ProxmoxSpec

from ccai.restclient.proxmox.specs.proxmoxvmclonespec import (
    ProxmoxVmCloneSpec
)
from ccai.restclient.proxmox.specs.proxmoxdiskspec import ProxmoxDiskSpec


# The base VMID the venue allocates clones from; each new VM takes the
# lowest free id at or above this floor.
_VMID_FLOOR: int = 9000


class PveApplyResult:
    """
        Accumulator carrying the created / updated / skipped resources
        produced by the Proxmox apply stages plus the VPN-device records
        the destroy stage must clean up.
    """

    def __init__(self) -> None:
        """
            Construct an empty PveApplyResult.
        """
        self.created: List[ProvisionedResource] = []
        self.updated: List[ProvisionedResource] = []
        self.skipped: List[str] = []
        self.vpn_records: List[Dict[str, Any]] = []
        return


class PveApplyStages:
    """
        The Proxmox VE apply stages.

        Apply runs Network (bridge) -> Firewall (per-VM SG rules) ->
        VM clone-from-template -> disk attach -> cloud-init config drive ->
        power-on.  Every stage is idempotent: a resource already realised
        in shape is a SKIP and no mutating call is issued.
    """

    def __init__(self, *, client: Any, resolver: PveResolver,
                 cloud_init_renderer: Optional[PveCloudInitRenderer] = None
                 ) -> None:
        """
            Construct a PveApplyStages.

            :param client: The Proxmox interop client.
            :param resolver: The :class:`PveResolver`.
            :param cloud_init_renderer: Optional :class:`PveCloudInitRenderer`;
                defaults to a fresh renderer bound to the client.
        """
        self._client = client
        self._resolver = resolver
        if cloud_init_renderer is not None:
            self._cloud_init_renderer = cloud_init_renderer
        else:
            self._cloud_init_renderer = PveCloudInitRenderer(client=client)
        return

    def apply_networking(self, *, spec: ProxmoxSpec, result: PveApplyResult,
                          aspects: Any) -> None:
        """
            Ensure every CloudNetwork is realised as a Linux bridge.

            :param spec: The :class:`ProxmoxSpec`.
            :param result: The :class:`PveApplyResult` accumulator.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        node = self._resolver.default_node
        if node is None:
            return

        for network in spec.networks:
            created = self._client.networks.create_bridge(
                node_name=node, bridge=network.name, cidr=network.cidr,
                comments="ccai network {}".format(network.name),
                aspects=aspects,
            )
            if created is True:
                result.created.append(ProvisionedResource(
                    kind="network", name=network.name,
                    venue_id="{}:{}".format(node, network.name),
                    attributes={"bridge": network.name, "node": node},
                ))
            else:
                result.skipped.append(network.name)
        return

    def apply_vms(self, *, spec: ProxmoxSpec, run_id: str,
                  result: PveApplyResult,
                  vpn_control_plane: Optional[Any], aspects: Any) -> None:
        """
            Clone, configure, tag, and power-on each VM idempotently.

            :param spec: The :class:`ProxmoxSpec`.
            :param run_id: The provisioning run id.
            :param result: The :class:`PveApplyResult` accumulator.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl used
                to mint VPN auth keys.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        live_by_name = self._live_vms_by_name(run_id=run_id, aspects=aspects)
        used_vmids = self._used_vmids(aspects=aspects)

        for inst in spec.instances:
            venue_name = vm_name_for(spec_name=inst.name, run_id=run_id)
            existing = live_by_name.get(venue_name, None)

            node = self._resolver.resolve_node(instance=inst)
            if node is None:
                continue

            if existing is not None:
                drifted = self._vm_has_drifted(inst=inst, existing=existing)
                if drifted is not True:
                    result.skipped.append(inst.name)
                    self._record_vpn(inst=inst, vmid=existing.vmid,
                                     result=result)
                    continue
                # Proxmox exposes no public in-place vCPU / memory
                # reconfigure on the interop client; a drifted VM is
                # realised UPDATE-by-recreate — stop + destroy the stale
                # VM, then re-clone it at the desired hardware shape.
                self._recreate_vm(spec=spec, inst=inst, run_id=run_id,
                                  venue_name=venue_name, node=node,
                                  existing=existing, used_vmids=used_vmids,
                                  result=result,
                                  vpn_control_plane=vpn_control_plane,
                                  aspects=aspects)
                continue

            resource = self._provision_vm(
                spec=spec, inst=inst, run_id=run_id, venue_name=venue_name,
                node=node, used_vmids=used_vmids,
                vpn_control_plane=vpn_control_plane, result=result,
                aspects=aspects,
            )
            result.created.append(resource)
        return

    def _vm_has_drifted(self, *, inst: CloudInstance,
                        existing: Any) -> bool:
        """
            Return whether a live VM's cores / memory drifts from the
            spec's resolved hardware shape.

            :param inst: The neutral :class:`CloudInstance`.
            :param existing: The live :class:`ProxmoxVmStatus`.

            :returns: ``True`` when the VM has drifted.
        """
        hardware = self._resolver.size_to_hardware(size_hint=inst.size)
        drifted = False
        if existing.cpus is not None:
            if int(existing.cpus) != hardware.cores:
                drifted = True
        if existing.maxmem is not None:
            desired_bytes = hardware.memory_mb * 1024 * 1024
            if int(existing.maxmem) != desired_bytes:
                drifted = True
        rtnval = drifted
        return rtnval

    def _recreate_vm(self, *, spec: ProxmoxSpec, inst: CloudInstance,
                     run_id: str, venue_name: str, node: str,
                     existing: Any, used_vmids: set,
                     result: PveApplyResult,
                     vpn_control_plane: Optional[Any],
                     aspects: Any) -> None:
        """
            Realise a drifted VM UPDATE-by-recreate — stop + destroy the
            stale VM, then re-clone it at the desired hardware shape.

            :param spec: The :class:`ProxmoxSpec`.
            :param inst: The neutral :class:`CloudInstance`.
            :param run_id: The provisioning run id.
            :param venue_name: The venue-side VM name.
            :param node: The node hosting the VM.
            :param existing: The live :class:`ProxmoxVmStatus`.
            :param used_vmids: The mutable in-use VMID set.
            :param result: The :class:`PveApplyResult` accumulator.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        stop_handle = self._client.qemu.stop_vm(node_name=node,
                                                vmid=existing.vmid,
                                                aspects=aspects)
        if stop_handle is not None:
            stop_handle.wait(aspects=aspects, raise_on_failure=False)
        destroy_handle = self._client.qemu.destroy_vm(node_name=node,
                                                      vmid=existing.vmid,
                                                      aspects=aspects)
        if destroy_handle is not None:
            destroy_handle.wait(aspects=aspects, raise_on_failure=False)
        used_vmids.discard(existing.vmid)

        resource = self._provision_vm(
            spec=spec, inst=inst, run_id=run_id, venue_name=venue_name,
            node=node, used_vmids=used_vmids,
            vpn_control_plane=vpn_control_plane, result=result,
            aspects=aspects,
        )
        result.updated.append(resource)
        return

    def _provision_vm(self, *, spec: ProxmoxSpec, inst: CloudInstance,
                      run_id: str, venue_name: str, node: str,
                      used_vmids: set,
                      vpn_control_plane: Optional[Any],
                      result: PveApplyResult,
                      aspects: Any) -> ProvisionedResource:
        """
            Clone, configure, tag, and power-on a single VM.

            :param spec: The :class:`ProxmoxSpec`.
            :param inst: The neutral :class:`CloudInstance`.
            :param run_id: The provisioning run id.
            :param venue_name: The venue-side VM name.
            :param node: The node hosting the VM.
            :param used_vmids: The mutable in-use VMID set.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl.
            :param result: The :class:`PveApplyResult` accumulator.
            :param aspects: Behaviour control for the interop client.

            :returns: The :class:`ProvisionedResource` for the VM.
        """
        image_resolution = self._resolver.image_to_template_or_url(
            image=inst.image
        )
        hardware = self._resolver.size_to_hardware(size_hint=inst.size)

        new_vmid = self._next_vmid(used_vmids=used_vmids)
        used_vmids.add(new_vmid)

        tags = self._compose_tags(inst=inst, run_id=run_id)
        clone_spec = ProxmoxVmCloneSpec(
            newid=new_vmid, name=venue_name, full=True,
            target_node=node,
            storage=self._resolver.pick_storage(
                required_gb=hardware.disk_gb, node=node
            ),
            description="ccai {}".format(run_id),
            extra={"cores": hardware.cores, "memory": hardware.memory_mb},
        )
        clone_handle = self._client.qemu.clone_vm(
            node_name=node, source_vmid=image_resolution.template_vmid,
            spec=clone_spec, aspects=aspects,
        )
        clone_handle.wait(aspects=aspects)

        self._client.qemu.set_tags(node_name=node, vmid=new_vmid,
                                   tags=tags, aspects=aspects)

        self._apply_disks(spec=spec, inst=inst, node=node,
                          vmid=new_vmid, aspects=aspects)

        authkey = self._mint_authkey(inst=inst,
                                     vpn_control_plane=vpn_control_plane)
        snippet = self._cloud_init_renderer.render_and_upload(
            node_name=node, instance=inst, keypairs=spec.keypairs,
            rendered_hostname=venue_name, authkey=authkey,
            aspects=aspects,
        )
        if snippet is not None:
            self._client.qemu.set_cloud_init_user_data(
                node_name=node, vmid=new_vmid,
                user_data=snippet.cicustom_value, aspects=aspects,
            )

        if inst.subnet is not None and len(inst.subnet) > 0:
            self._client.qemu.set_ip_config(
                node_name=node, vmid=new_vmid, slot="ipconfig0",
                value="ip=dhcp", aspects=aspects,
            )

        self._attach_firewall(spec=spec, inst=inst, node=node,
                              vmid=new_vmid, aspects=aspects)

        start_handle = self._client.qemu.start_vm(
            node_name=node, vmid=new_vmid, aspects=aspects
        )
        start_handle.wait(aspects=aspects)

        resource = ProvisionedResource(
            kind="instance", name=inst.name,
            venue_id=str(new_vmid),
            attributes={"vmid": new_vmid, "node": node,
                        "venue_name": venue_name,
                        "cores": hardware.cores,
                        "memory_mb": hardware.memory_mb},
            tags=inst.tags if inst.tags is not None else {},
        )
        self._record_vpn(inst=inst, vmid=new_vmid, result=result)
        rtnval = resource
        return rtnval

    def _apply_disks(self, *, spec: ProxmoxSpec, inst: CloudInstance,
                     node: str, vmid: int, aspects: Any) -> None:
        """
            Attach every CloudStorageVolume bound to an instance.

            :param spec: The :class:`ProxmoxSpec`.
            :param inst: The neutral :class:`CloudInstance`.
            :param node: The node hosting the VM.
            :param vmid: The numeric VM identifier.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        slot_index = 1
        for volume in spec.volumes:
            if volume.attached_to != inst.name:
                continue
            storage = self._resolver.pick_storage(
                required_gb=volume.size_gb, node=node
            )
            disk_spec = ProxmoxDiskSpec(
                slot="scsi{}".format(slot_index), storage=storage,
                size_gb=volume.size_gb,
            )
            self._client.qemu.attach_disk(node_name=node, vmid=vmid,
                                          spec=disk_spec, aspects=aspects)
            slot_index = slot_index + 1
        return

    def _attach_firewall(self, *, spec: ProxmoxSpec, inst: CloudInstance,
                         node: str, vmid: int, aspects: Any) -> None:
        """
            Attach the firewall rules of every bound CloudSecurityGroup.

            :param spec: The :class:`ProxmoxSpec`.
            :param inst: The neutral :class:`CloudInstance`.
            :param node: The node hosting the VM.
            :param vmid: The numeric VM identifier.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        instance_groups = inst.security_groups
        if instance_groups is None or len(instance_groups) == 0:
            return

        from ccai.restclient.proxmox.specs.proxmoxfirewallrulespec import (
            ProxmoxFirewallRuleSpec
        )

        for sg in spec.security_groups:
            if sg.name not in instance_groups:
                continue
            for rule in self._security_group_rules(sg=sg):
                rule_spec = ProxmoxFirewallRuleSpec(
                    action=rule["action"], rule_type=rule["type"],
                    enable=True, proto=rule["proto"], dport=rule["dport"],
                    comment="ccai sg {}".format(sg.name),
                )
                self._client.firewall.add_vm_firewall_rule(
                    node_name=node, vmid=vmid, spec=rule_spec,
                    aspects=aspects,
                )
        return

    @staticmethod
    def _security_group_rules(*, sg: Any) -> List[Dict[str, Any]]:
        """
            Translate a CloudSecurityGroup into Proxmox firewall rule dicts.

            :param sg: The neutral :class:`CloudSecurityGroup`.

            :returns: A list of rule dicts.
        """
        rules: List[Dict[str, Any]] = []
        ingress = getattr(sg, "ingress_rules", None)
        if ingress is not None:
            for entry in ingress:
                from_port = getattr(entry, "from_port", 0)
                to_port = getattr(entry, "to_port", from_port)
                if from_port == to_port:
                    dport = str(from_port)
                else:
                    dport = "{}:{}".format(from_port, to_port)
                rules.append({
                    "action": "ACCEPT", "type": "in",
                    "proto": getattr(entry, "protocol", "tcp"),
                    "dport": dport,
                })
        rtnval = rules
        return rtnval

    def _compose_tags(self, *, inst: CloudInstance, run_id: str) -> List[str]:
        """
            Compose the Proxmox tag list for a VM.

            :param inst: The neutral :class:`CloudInstance`.
            :param run_id: The provisioning run id.

            :returns: The ordered Proxmox tag-string list.
        """
        tags: List[str] = [OWNER_TAG, run_id_tag(run_id=run_id)]
        neutral = inst.tags if inst.tags is not None else {}
        for encoded in PveTagTranslator.to_pve(neutral_tags=neutral):
            tags.append(encoded)
        return tags

    @staticmethod
    def _mint_authkey(*, inst: CloudInstance,
                      vpn_control_plane: Optional[Any]) -> str:
        """
            Mint the VPN auth key for an instance that carries a vpn_join.

            :param inst: The neutral :class:`CloudInstance`.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl.

            :returns: The minted auth key, or an empty string.
        """
        authkey = ""
        if inst.vpn_join is not None and vpn_control_plane is not None:
            candidate = getattr(vpn_control_plane, "minted_authkey", "")
            if candidate is not None:
                authkey = candidate
        return authkey

    @staticmethod
    def _record_vpn(*, inst: CloudInstance, vmid: int,
                    result: PveApplyResult) -> None:
        """
            Record a VPN-device entry for a VPN-joined instance.

            :param inst: The neutral :class:`CloudInstance`.
            :param vmid: The numeric VM identifier.
            :param result: The :class:`PveApplyResult` accumulator.

            :returns: ``None``.
        """
        if inst.vpn_join is None:
            return
        result.vpn_records.append({
            "instance_name": inst.name,
            "vmid": vmid,
            "vpn_provider": inst.vpn_join.provider,
            "vpn_device_id": inst.name,
        })
        return

    def _live_vms_by_name(self, *, run_id: str,
                          aspects: Any) -> Dict[str, Any]:
        """
            List run-owned VMs across every node, keyed by venue-side name.

            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.

            :returns: A dict of venue-side VM name to VM-status record.
        """
        rtnval: Dict[str, Any] = {}
        for node in self._client.nodes.list(aspects=aspects):
            for vm in self._client.qemu.list_vms(node_name=node.name,
                                                 aspects=aspects):
                if has_run_id_tag(tags=vm.tags, run_id=run_id) is not True:
                    continue
                if vm.name is not None:
                    rtnval[vm.name] = vm
        return rtnval

    def _used_vmids(self, *, aspects: Any) -> set:
        """
            Collect every VMID in use across the cluster.

            :param aspects: Behaviour control for the interop client.

            :returns: A set of in-use numeric VMIDs.
        """
        used: set = set()
        for node in self._client.nodes.list(aspects=aspects):
            for vm in self._client.qemu.list_vms(node_name=node.name,
                                                 aspects=aspects):
                used.add(vm.vmid)
        rtnval = used
        return rtnval

    @staticmethod
    def _next_vmid(*, used_vmids: set) -> int:
        """
            Return the lowest free VMID at or above the venue floor.

            :param used_vmids: The set of in-use VMIDs.

            :returns: A free numeric VMID.
        """
        candidate = _VMID_FLOOR
        while candidate in used_vmids:
            candidate = candidate + 1
        rtnval = candidate
        return rtnval
