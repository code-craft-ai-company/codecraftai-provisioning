"""
    .. module:: llapplystages
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: LlApplyStages — the SSH-key and instance/cluster apply
               stages for the Lambda Labs venue provisioner.

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
from ccai.provisioning.venues.lambdalabs.llnaming import instance_name_for
from ccai.provisioning.venues.lambdalabs.llresolver import LlResolver
from ccai.provisioning.venues.lambdalabs.llsidecartag import LlSidecarTag
from ccai.provisioning.venues.lambdalabs.lluserdatarenderer import (
    LlUserDataRenderer
)
from ccai.provisioning.venues.lambdalabs.lambdalabsspec import (
    LambdalabsSpec
)

from ccai.restclient.lambdalabs.specs.lambdalabsclusterspec import (
    LambdalabsClusterSpec
)
from ccai.restclient.lambdalabs.specs.lambdalabslaunchspec import (
    LambdalabsLaunchSpec
)


class LlApplyResult:
    """
        Accumulator carrying the created / skipped resources produced by
        the Lambda Labs apply stages plus the VPN-device records the
        destroy stage must clean up.
    """

    def __init__(self) -> None:
        """
            Construct an empty LlApplyResult.
        """
        self.created: List[ProvisionedResource] = []
        self.skipped: List[str] = []
        self.vpn_records: List[Dict[str, Any]] = []
        return


class LlApplyStages:
    """
        The Lambda Labs apply stages.

        Stage one ensures every SSH key is uploaded; stage two launches
        each instance (or 1-click cluster), rendering the launch
        ``user_data`` field from the M6 cloud-init renderer when the
        instance carries a ``vpn_join`` spec.  Both stages are idempotent
        — a launched instance whose venue-side name already exists is a
        SKIP and no mutating call is issued.
    """

    def __init__(self, *, client: Any, resolver: LlResolver,
                 user_data_renderer: Optional[LlUserDataRenderer] = None
                 ) -> None:
        """
            Construct an LlApplyStages.

            :param client: The Lambda Labs interop client.
            :param resolver: The :class:`LlResolver`.
            :param user_data_renderer: Optional :class:`LlUserDataRenderer`;
                defaults to a fresh instance.
        """
        self._client = client
        self._resolver = resolver
        if user_data_renderer is not None:
            self._user_data_renderer = user_data_renderer
        else:
            self._user_data_renderer = LlUserDataRenderer()
        return

    def ensure_ssh_keys(self, *, spec: LambdalabsSpec, result: LlApplyResult,
                        aspects: Any) -> None:
        """
            Ensure every SSH key in the spec is registered.

            :param spec: The :class:`LambdalabsSpec`.
            :param result: The :class:`LlApplyResult` accumulator.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        live_keys = self._client.list_ssh_keys(aspects=aspects)
        live_names: List[str] = []
        for key in live_keys:
            live_names.append(key.name)

        for keypair in spec.keypairs:
            existed = keypair.name in live_names
            registered = self._client.register_ssh_key(
                name=keypair.name,
                public_key=keypair.public_key_material,
                aspects=aspects,
            )
            resource = ProvisionedResource(
                kind="keypair", name=keypair.name,
                venue_id=registered.identifier,
                attributes={"ssh_key_id": registered.identifier},
            )
            if existed:
                result.skipped.append(keypair.name)
            else:
                result.created.append(resource)
        return

    def apply_instances(self, *, spec: LambdalabsSpec, run_id: str,
                        result: LlApplyResult,
                        vpn_control_plane: Optional[Any],
                        sidecar: LlSidecarTag, aspects: Any) -> None:
        """
            Launch each instance, branching to the 1-click cluster API for
            multi-node InfiniBand requests.

            :param spec: The :class:`LambdalabsSpec`.
            :param run_id: The provisioning run id.
            :param result: The :class:`LlApplyResult` accumulator.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl
                used to mint VPN auth keys.
            :param sidecar: The :class:`LlSidecarTag` tag store.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        live_instances = self._client.list_instances(aspects=aspects)
        live_by_name: Dict[str, Any] = {}
        for instance in live_instances:
            live_by_name[instance.name] = instance

        fs_names = self._filesystem_names(spec=spec, aspects=aspects)

        for inst in spec.instances:
            venue_name = instance_name_for(spec_name=inst.name,
                                           run_id=run_id)
            existing = live_by_name.get(venue_name, None)
            if existing is not None:
                result.skipped.append(inst.name)
                continue

            resolution = self._resolver.resolve_instance_type(instance=inst)
            if resolution is None:
                continue

            user_data = self._render_user_data(
                inst=inst, venue_name=venue_name,
                vpn_control_plane=vpn_control_plane, aspects=aspects,
            )

            ssh_key_names = list(inst.security_groups) if False else []
            if inst.keypair is not None:
                ssh_key_names = [inst.keypair]

            if resolution.is_cluster:
                resource = self._launch_cluster(
                    inst=inst, venue_name=venue_name, resolution=resolution,
                    ssh_key_names=ssh_key_names, fs_names=fs_names,
                    user_data=user_data, aspects=aspects,
                )
            else:
                resource = self._launch_instance(
                    inst=inst, venue_name=venue_name, resolution=resolution,
                    ssh_key_names=ssh_key_names, fs_names=fs_names,
                    user_data=user_data, aspects=aspects,
                )

            result.created.append(resource)

            tags = inst.tags if inst.tags is not None else {}
            sidecar.write(neutral_tags=tags,
                          instance_id=resource.venue_id)

            if inst.vpn_join is not None:
                result.vpn_records.append({
                    "instance_name": inst.name,
                    "instance_id": resource.venue_id,
                    "vpn_provider": inst.vpn_join.provider,
                    "vpn_device_id": resource.attributes.get(
                        "vpn_device_id", None
                    ),
                })
        return

    def _filesystem_names(self, *, spec: LambdalabsSpec,
                          aspects: Any) -> List[str]:
        """
            Resolve the attach-list of Lambda Labs file-system names.

            :param spec: The :class:`LambdalabsSpec`.
            :param aspects: Behaviour control for the interop client.

            :returns: The list of file-system names to attach.
        """
        names: List[str] = []
        if len(spec.shared_filesystems) == 0:
            rtnval = names
            return rtnval

        live = self._client.list_filesystems(aspects=aspects)
        live_by_id: Dict[str, Any] = {}
        for filesystem in live:
            live_by_id[filesystem.identifier] = filesystem

        for sfs in spec.shared_filesystems:
            existing = live_by_id.get(sfs.existing_id, None)
            if existing is not None:
                names.append(existing.name)
        rtnval = names
        return rtnval

    def _render_user_data(self, *, inst: CloudInstance, venue_name: str,
                          vpn_control_plane: Optional[Any],
                          aspects: Any) -> Optional[str]:
        """
            Render the launch ``user_data`` field for an instance.

            :param inst: The neutral :class:`CloudInstance`.
            :param venue_name: The venue-side instance name (hostname).
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl.
            :param aspects: Behaviour control (unused here, retained for
                interface uniformity).

            :returns: The ``user_data`` string, or ``None``.
        """
        # `aspects` retained for interface uniformity with the other
        # stage helpers; the renderer itself is pure.
        _ = aspects

        authkey = ""
        if inst.vpn_join is not None and vpn_control_plane is not None:
            authkey = getattr(vpn_control_plane, "minted_authkey", "")
            if authkey is None:
                authkey = ""

        rtnval = self._user_data_renderer.render(
            instance=inst, authkey=authkey, rendered_hostname=venue_name
        )
        return rtnval

    def _launch_instance(self, *, inst: CloudInstance, venue_name: str,
                         resolution: Any, ssh_key_names: List[str],
                         fs_names: List[str], user_data: Optional[str],
                         aspects: Any) -> ProvisionedResource:
        """
            Launch a single Lambda Labs instance.

            :param inst: The neutral :class:`CloudInstance`.
            :param venue_name: The venue-side instance name.
            :param resolution: The :class:`LlResolutionResult`.
            :param ssh_key_names: SSH key names to attach.
            :param fs_names: File-system names to attach.
            :param user_data: The launch ``user_data`` payload.
            :param aspects: Behaviour control for the interop client.

            :returns: A :class:`ProvisionedResource` for the instance.
        """
        # The instance's region is sourced from the image owner field when
        # present; otherwise the CloudInstance.profile_ref carries no
        # region, so the spec-level region (size) default is used.
        region = self._region_for(inst=inst)
        launch_spec = LambdalabsLaunchSpec(
            region_name=region,
            instance_type_name=resolution.instance_type_slug,
            ssh_key_names=ssh_key_names, file_system_names=fs_names,
            name=venue_name, quantity=1, user_data=user_data,
        )
        launched = self._client.launch_instances(spec=launch_spec,
                                                  aspects=aspects)
        first = launched[0]
        rtnval = ProvisionedResource(
            kind="instance", name=inst.name, venue_id=first.identifier,
            attributes={"instance_id": first.identifier,
                        "instance_type": first.instance_type_name,
                        "status": first.status,
                        "venue_name": venue_name},
            tags=inst.tags if inst.tags is not None else {},
        )
        return rtnval

    def _launch_cluster(self, *, inst: CloudInstance, venue_name: str,
                        resolution: Any, ssh_key_names: List[str],
                        fs_names: List[str], user_data: Optional[str],
                        aspects: Any) -> ProvisionedResource:
        """
            Launch a Lambda Labs 1-click cluster.

            :param inst: The neutral :class:`CloudInstance`.
            :param venue_name: The venue-side cluster name.
            :param resolution: The :class:`LlResolutionResult`.
            :param ssh_key_names: SSH key names to attach.
            :param fs_names: File-system names to attach.
            :param user_data: The launch ``user_data`` payload.
            :param aspects: Behaviour control for the interop client.

            :returns: A :class:`ProvisionedResource` for the cluster.
        """
        region = self._region_for(inst=inst)
        node_count = 1
        if inst.accelerators is not None and len(inst.accelerators) > 0:
            node_count = max(1, len(inst.accelerators))

        cluster_spec = LambdalabsClusterSpec(
            name=venue_name, region_name=region,
            instance_type_name=resolution.instance_type_slug,
            node_count=node_count, ssh_key_names=ssh_key_names,
            file_system_names=fs_names, user_data=user_data,
        )
        cluster = self._client.create_cluster(spec=cluster_spec,
                                              aspects=aspects)
        rtnval = ProvisionedResource(
            kind="cluster", name=inst.name, venue_id=cluster.identifier,
            attributes={"cluster_id": cluster.identifier,
                        "instance_type": cluster.instance_type_name,
                        "instance_ids": list(cluster.instance_ids),
                        "status": cluster.status,
                        "venue_name": venue_name},
            tags=inst.tags if inst.tags is not None else {},
        )
        return rtnval

    @staticmethod
    def _region_for(*, inst: CloudInstance) -> str:
        """
            Resolve the Lambda Labs region for an instance.

            The neutral :class:`CloudInstance` carries no first-class
            region field; Lambda Labs needs one, so the renderer reads the
            instance ``subnet`` field, which the Lambda Labs venue treats
            as the region name (see the venue mapping table).

            :param inst: The neutral :class:`CloudInstance`.

            :returns: The Lambda Labs region name.
        """
        rtnval = inst.subnet
        return rtnval
