"""
    .. module:: ntxapplystages
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: NtxApplyStages — the network / flow-policy / volume / VM apply
               stages for the Nutanix venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.provisioning.model.cloud.cloudinstance import CloudInstance
from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)

from automojo.provisioning.venues.nutanix.nutanixspec import NutanixSpec
from automojo.provisioning.venues.nutanix.nutanixvenueconfig import (
    NutanixVenueConfig
)
from automojo.provisioning.venues.nutanix.ntxcategorytranslator import (
    NtxCategoryTranslator
)
from automojo.provisioning.venues.nutanix.ntxcloudinitrenderer import (
    NtxCloudInitRenderer
)
from automojo.provisioning.venues.nutanix.ntxnaming import resource_name_for
from automojo.provisioning.venues.nutanix.ntxresolver import NtxResolver

from automojo.restclient.nutanix.specs.nutanixspecs import (
    SecurityPolicySpec, SubnetSpec, VmSpec, VolumeGroupSpec, VpcSpec
)


# Mebibytes per gibibyte for neutral GB volume sizing.
_MIB_PER_GIB = 1024


class NtxApplyResult:
    """
        Accumulator carrying the created / skipped resources produced by
        the Nutanix apply stages plus the VPN-device records the destroy
        stage must clean up.
    """

    def __init__(self) -> None:
        """
            Construct an empty NtxApplyResult.
        """
        self.created: List[ProvisionedResource] = []
        self.skipped: List[str] = []
        self.vpn_records: List[Dict[str, Any]] = []
        return


class NtxApplyStages:
    """
        The Nutanix apply stages.

        Apply runs in dependency order: Flow VPCs → Subnets → Flow
        security policies → Volume Groups → Image verification + VM clone
        (cloud-init guest customisation) → power-on.  Every Prism mutating
        call returns an ``ergon`` task handle awaited via the handle's
        poll loop with the supplied aspects.  Every stage is idempotent —
        a resource whose venue-side name already exists is a SKIP.
    """

    def __init__(self, *, client: Any, config: NutanixVenueConfig,
                 resolver: Optional[NtxResolver] = None,
                 category_translator: Optional[
                     NtxCategoryTranslator] = None,
                 cloud_init_renderer: Optional[
                     NtxCloudInitRenderer] = None) -> None:
        """
            Construct an NtxApplyStages.

            :param client: The Nutanix interop client.
            :param config: The :class:`NutanixVenueConfig`.
            :param resolver: Optional :class:`NtxResolver`.
            :param category_translator: Optional
                :class:`NtxCategoryTranslator`.
            :param cloud_init_renderer: Optional
                :class:`NtxCloudInitRenderer`.
        """
        self._client = client
        self._config = config
        if resolver is not None:
            self._resolver: NtxResolver = resolver
        else:
            self._resolver = NtxResolver(client=client, config=config)
        if category_translator is not None:
            self._category_translator: NtxCategoryTranslator = (
                category_translator
            )
        else:
            self._category_translator = NtxCategoryTranslator(client=client)
        if cloud_init_renderer is not None:
            self._cloud_init_renderer: NtxCloudInitRenderer = (
                cloud_init_renderer
            )
        else:
            self._cloud_init_renderer = NtxCloudInitRenderer()
        return

    def apply_network_and_flow_policies(self, *, spec: NutanixSpec,
                                        run_id: str,
                                        result: NtxApplyResult,
                                        aspects: Any) -> None:
        """
            Create the run's Flow VPCs, subnets and security policies.

            :param spec: The :class:`NutanixSpec`.
            :param run_id: The provisioning run id.
            :param result: The :class:`NtxApplyResult` accumulator.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        cluster_uuid = self._resolver.pick_cluster(aspects=aspects)

        self._apply_vpcs(spec=spec, run_id=run_id, result=result,
                         aspects=aspects)
        self._apply_subnets(spec=spec, run_id=run_id,
                            cluster_uuid=cluster_uuid, result=result,
                            aspects=aspects)
        self._apply_security_policies(spec=spec, run_id=run_id,
                                      result=result, aspects=aspects)
        return

    def _apply_vpcs(self, *, spec: NutanixSpec, run_id: str,
                    result: NtxApplyResult, aspects: Any) -> None:
        """
            Create the run's Flow VPCs.

            :param spec: The :class:`NutanixSpec`.
            :param run_id: The provisioning run id.
            :param result: The :class:`NtxApplyResult` accumulator.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        live = self._client.vpcs.list(aspects=aspects)
        live_names: List[str] = []
        for vpc in live:
            live_names.append(vpc.name)

        for network in spec.networks:
            venue_name = resource_name_for(spec_name=network.name,
                                           run_id=run_id)
            existed = venue_name in live_names

            vpc_spec = VpcSpec(name=venue_name)
            handle = self._client.vpcs.create(spec=vpc_spec,
                                              aspects=aspects)
            entity_uuid = handle.result_entity_uuid(aspects=aspects)
            if entity_uuid is None:
                entity_uuid = handle.task_id()

            resource = ProvisionedResource(
                kind="network", name=network.name, venue_id=entity_uuid,
                attributes={"venue_name": venue_name,
                            "cidr": network.cidr},
                tags=network.tags if network.tags is not None else [],
            )
            if existed:
                result.skipped.append(network.name)
            else:
                result.created.append(resource)
        return

    def _apply_subnets(self, *, spec: NutanixSpec, run_id: str,
                       cluster_uuid: str, result: NtxApplyResult,
                       aspects: Any) -> None:
        """
            Create the run's Prism subnets.

            :param spec: The :class:`NutanixSpec`.
            :param run_id: The provisioning run id.
            :param cluster_uuid: The placement cluster uuid.
            :param result: The :class:`NtxApplyResult` accumulator.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        live = self._client.subnets.list(aspects=aspects)
        live_names: List[str] = []
        for subnet in live:
            live_names.append(subnet.name)

        for subnet in spec.subnets:
            venue_name = resource_name_for(spec_name=subnet.name,
                                           run_id=run_id)
            existed = venue_name in live_names

            ip_config: Dict[str, Any] = {"subnet_ip": subnet.cidr}
            subnet_spec = SubnetSpec(name=venue_name,
                                     cluster_uuid=cluster_uuid,
                                     subnet_type="VLAN",
                                     ip_config=ip_config)
            handle = self._client.subnets.create(spec=subnet_spec,
                                                 aspects=aspects)
            entity_uuid = handle.result_entity_uuid(aspects=aspects)
            if entity_uuid is None:
                entity_uuid = handle.task_id()

            resource = ProvisionedResource(
                kind="subnet", name=subnet.name, venue_id=entity_uuid,
                attributes={"venue_name": venue_name,
                            "cidr": subnet.cidr,
                            "cluster_uuid": cluster_uuid},
                tags=subnet.tags if subnet.tags is not None else [],
            )
            if existed:
                result.skipped.append(subnet.name)
            else:
                result.created.append(resource)
        return

    def _apply_security_policies(self, *, spec: NutanixSpec, run_id: str,
                                 result: NtxApplyResult,
                                 aspects: Any) -> None:
        """
            Create the run's Flow security policies.

            :param spec: The :class:`NutanixSpec`.
            :param run_id: The provisioning run id.
            :param result: The :class:`NtxApplyResult` accumulator.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        live = self._client.security_policies.list(aspects=aspects)
        live_names: List[str] = []
        for policy in live:
            live_names.append(policy.name)

        for sg in spec.security_groups:
            venue_name = resource_name_for(spec_name=sg.name,
                                           run_id=run_id)
            existed = venue_name in live_names

            policy_spec = SecurityPolicySpec(name=venue_name, rules={})
            handle = self._client.security_policies.create(
                spec=policy_spec, aspects=aspects
            )
            entity_uuid = handle.result_entity_uuid(aspects=aspects)
            if entity_uuid is None:
                entity_uuid = handle.task_id()

            resource = ProvisionedResource(
                kind="security_group", name=sg.name,
                venue_id=entity_uuid,
                attributes={"venue_name": venue_name},
                tags=sg.tags if sg.tags is not None else [],
            )
            if existed:
                result.skipped.append(sg.name)
            else:
                result.created.append(resource)
        return

    def apply_volumes(self, *, spec: NutanixSpec, run_id: str,
                      result: NtxApplyResult, aspects: Any) -> None:
        """
            Create the run's volume groups for additional disks.

            :param spec: The :class:`NutanixSpec`.
            :param run_id: The provisioning run id.
            :param result: The :class:`NtxApplyResult` accumulator.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        live = self._client.volume_groups.list(aspects=aspects)
        live_names: List[str] = []
        for volume_group in live:
            live_names.append(volume_group.name)

        for volume in spec.volumes:
            venue_name = resource_name_for(spec_name=volume.name,
                                           run_id=run_id)
            existed = venue_name in live_names

            disk_size_mib = volume.size_gb * _MIB_PER_GIB
            volume_group_spec = VolumeGroupSpec(
                name=venue_name, disk_size_mib=disk_size_mib,
                storage_container_uuid=self._config.storage_container_uuid,
            )
            handle = self._client.volume_groups.create(
                spec=volume_group_spec, aspects=aspects
            )
            entity_uuid = handle.result_entity_uuid(aspects=aspects)
            if entity_uuid is None:
                entity_uuid = handle.task_id()

            resource = ProvisionedResource(
                kind="volume", name=volume.name, venue_id=entity_uuid,
                attributes={"venue_name": venue_name,
                            "size_gb": volume.size_gb,
                            "storage_class": volume.storage_class.value},
                tags=volume.tags if volume.tags is not None else [],
            )
            if existed:
                result.skipped.append(volume.name)
            else:
                result.created.append(resource)
        return

    def apply_vms(self, *, spec: NutanixSpec, run_id: str,
                  result: NtxApplyResult,
                  vpn_control_plane: Optional[Any],
                  aspects: Any) -> None:
        """
            Verify images and clone + power-on the run's VMs.

            A VM carrying a :class:`VPNJoinSpec` has the VPN-join
            cloud-init snippet rendered into its
            ``guest_customization.cloud_init.user_data`` (base64-encoded).

            :param spec: The :class:`NutanixSpec`.
            :param run_id: The provisioning run id.
            :param result: The :class:`NtxApplyResult` accumulator.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl
                used to mint VPN auth keys.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        cluster_uuid = self._resolver.pick_cluster(aspects=aspects)

        live = self._client.vms.list(aspects=aspects)
        live_by_name: Dict[str, Any] = {}
        for vm in live:
            live_by_name[vm.name] = vm

        for instance in spec.instances:
            venue_name = resource_name_for(spec_name=instance.name,
                                           run_id=run_id)
            if venue_name in live_by_name:
                result.skipped.append(instance.name)
                continue

            image_uuid = self._resolver.image_to_uuid(
                family=instance.image.family,
                version=instance.image.version,
                arch=instance.image.architecture, aspects=aspects,
            )
            hardware = self._resolver.size_to_hardware(
                size_hint=instance.size
            )
            categories = self._category_translator.ensure(
                neutral_tags=instance.tags, run_id=run_id, aspects=aspects
            )
            subnet_uuids = self._subnet_uuids_for(spec=spec,
                                                  instance=instance,
                                                  run_id=run_id,
                                                  aspects=aspects)
            user_data = self._render_user_data(
                spec=spec, instance=instance, venue_name=venue_name,
                vpn_control_plane=vpn_control_plane,
            )

            vm_spec = VmSpec(
                name=venue_name, cluster_uuid=cluster_uuid,
                num_vcpus=hardware["num_vcpus"],
                num_cores_per_vcpu=hardware["num_cores_per_vcpu"],
                memory_mib=hardware["memory_mib"],
                subnet_uuids=subnet_uuids,
                boot_image_uuid=image_uuid,
                cloud_init_user_data=user_data,
                categories=categories, power_state="ON",
            )
            handle = self._client.vms.create(spec=vm_spec, aspects=aspects)
            vm_uuid = handle.result_entity_uuid(aspects=aspects)
            if vm_uuid is None:
                vm_uuid = handle.task_id()

            self._client.vms.power_on(vm_uuid=vm_uuid, aspects=aspects)

            resource = ProvisionedResource(
                kind="instance", name=instance.name, venue_id=vm_uuid,
                attributes={"venue_name": venue_name,
                            "uuid": vm_uuid,
                            "num_vcpus": hardware["num_vcpus"],
                            "memory_mib": hardware["memory_mib"],
                            "image_uuid": image_uuid,
                            "cluster_uuid": cluster_uuid},
                tags=instance.tags if instance.tags is not None else [],
            )
            result.created.append(resource)

            if instance.vpn_join is not None:
                result.vpn_records.append({
                    "instance_name": instance.name,
                    "instance_id": vm_uuid,
                    "venue_name": venue_name,
                    "vpn_provider": instance.vpn_join.provider,
                    "vpn_device_id": venue_name,
                })
        return

    def _subnet_uuids_for(self, *, spec: NutanixSpec,
                          instance: CloudInstance, run_id: str,
                          aspects: Any) -> List[str]:
        """
            Resolve the Prism subnet uuids a VM's NICs attach to.

            :param spec: The :class:`NutanixSpec`.
            :param instance: The neutral :class:`CloudInstance`.
            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.

            :returns: The list of subnet uuids; empty when no spec subnet
                matches the instance's named subnet.
        """
        rtnval: List[str] = []

        venue_subnet_name = resource_name_for(spec_name=instance.subnet,
                                              run_id=run_id)
        match = self._client.subnets.find_by_name(name=venue_subnet_name,
                                                  aspects=aspects)
        if match is not None:
            rtnval.append(match.uuid)
        return rtnval

    def _render_user_data(self, *, spec: NutanixSpec,
                          instance: CloudInstance, venue_name: str,
                          vpn_control_plane: Optional[Any]
                          ) -> Optional[str]:
        """
            Render the base64 cloud-init user_data for a VM.

            :param spec: The :class:`NutanixSpec`.
            :param instance: The neutral :class:`CloudInstance`.
            :param venue_name: The venue-side VM name / hostname.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl.

            :returns: The base64 user_data string, or ``None``.
        """
        authkey = ""
        if instance.vpn_join is not None and vpn_control_plane is not None:
            minted = getattr(vpn_control_plane, "minted_authkey", "")
            if minted is not None:
                authkey = minted

        rtnval = self._cloud_init_renderer.render(
            instance=instance, keypairs=spec.keypairs, authkey=authkey,
            rendered_hostname=venue_name,
        )
        return rtnval
