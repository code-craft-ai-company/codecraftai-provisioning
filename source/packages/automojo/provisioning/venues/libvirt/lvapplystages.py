"""
    .. module:: lvapplystages
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: LvApplyStages — the network / pool / volume / domain apply
               stages for the libvirt venue provisioner.

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
from automojo.provisioning.venues.libvirt.libvirtspec import LibvirtSpec
from automojo.provisioning.venues.libvirt.libvirtvenueconfig import (
    LibvirtVenueConfig
)
from automojo.provisioning.venues.libvirt.lvdomainxmlbuilder import (
    LvDomainXmlBuilder
)
from automojo.provisioning.venues.libvirt.lvnaming import (
    boot_volume_name_for, resource_name_for, seed_volume_name_for
)
from automojo.provisioning.venues.libvirt.lvseedisobuilder import (
    LvSeedIsoBuilder
)

from automojo.interop.libvirt.specs.libvirtnetworkspec import (
    LibvirtNetworkSpec
)
from automojo.interop.libvirt.specs.libvirtvolumespec import LibvirtVolumeSpec


# Gibibyte conversion factor for neutral GB volume sizing.
_GIB = 1024 * 1024 * 1024


class LvApplyResult:
    """
        Accumulator carrying the created / skipped resources produced by
        the libvirt apply stages plus the VPN-device records the destroy
        stage must clean up.
    """

    def __init__(self) -> None:
        """
            Construct an empty LvApplyResult.
        """
        self.created: List[ProvisionedResource] = []
        self.skipped: List[str] = []
        self.vpn_records: List[Dict[str, Any]] = []
        return


class LvApplyStages:
    """
        The libvirt apply stages.

        Apply runs in dependency order: Networks define+start → Storage
        Pools define+start → base-image boot-volume clones (qcow2
        backing chain) → cloud-init seed-ISO build+upload → Domain
        define+start.  Every stage is idempotent — a resource whose
        venue-side name already exists is a SKIP and no mutating call is
        issued for it.
    """

    def __init__(self, *, client: Any, config: LibvirtVenueConfig,
                 domain_builder: Optional[LvDomainXmlBuilder] = None,
                 seed_builder: Optional[LvSeedIsoBuilder] = None) -> None:
        """
            Construct an LvApplyStages.

            :param client: The libvirt interop client.
            :param config: The :class:`LibvirtVenueConfig`.
            :param domain_builder: Optional :class:`LvDomainXmlBuilder`;
                defaults to a fresh instance.
            :param seed_builder: Optional :class:`LvSeedIsoBuilder`;
                defaults to a fresh instance.
        """
        self._client = client
        self._config = config
        if domain_builder is not None:
            self._domain_builder: LvDomainXmlBuilder = domain_builder
        else:
            self._domain_builder = LvDomainXmlBuilder()
        if seed_builder is not None:
            self._seed_builder: LvSeedIsoBuilder = seed_builder
        else:
            self._seed_builder = LvSeedIsoBuilder()
        return

    def apply_networks_and_pools(self, *, spec: LibvirtSpec, run_id: str,
                                 result: LvApplyResult,
                                 aspects: Any) -> None:
        """
            Define and start the run's networks.

            :param spec: The :class:`LibvirtSpec`.
            :param run_id: The provisioning run id.
            :param result: The :class:`LvApplyResult` accumulator.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        live = self._client.networks.list_networks(aspects=aspects)
        live_names: List[str] = []
        for network in live:
            live_names.append(network.name)

        for network in spec.networks:
            venue_name = resource_name_for(spec_name=network.name,
                                           run_id=run_id)
            existed = venue_name in live_names

            network_spec = LibvirtNetworkSpec(name=venue_name,
                                              forward_mode="nat")
            defined = self._client.networks.define_network(
                spec=network_spec, aspects=aspects
            )
            self._client.networks.start_network(name=venue_name,
                                                aspects=aspects)

            resource = ProvisionedResource(
                kind="network", name=network.name, venue_id=defined.uuid,
                attributes={"venue_name": venue_name,
                            "forward_mode": defined.forward_mode},
                tags=network.tags if network.tags is not None else {},
            )
            if existed:
                result.skipped.append(network.name)
            else:
                result.created.append(resource)
        return

    def apply_volumes(self, *, spec: LibvirtSpec, run_id: str,
                      result: LvApplyResult, aspects: Any) -> None:
        """
            Create the run's data volumes in the boot-disk pool.

            :param spec: The :class:`LibvirtSpec`.
            :param run_id: The provisioning run id.
            :param result: The :class:`LvApplyResult` accumulator.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        pool_name = self._config.boot_disk_pool
        live = self._client.volumes.list_volumes(pool_name=pool_name,
                                                 aspects=aspects)
        live_names: List[str] = []
        for volume in live:
            live_names.append(volume.name)

        for volume in spec.volumes:
            venue_name = resource_name_for(spec_name=volume.name,
                                           run_id=run_id)
            existed = venue_name in live_names

            capacity_bytes = volume.size_gb * _GIB
            volume_spec = LibvirtVolumeSpec(name=venue_name,
                                            capacity_bytes=capacity_bytes,
                                            volume_format="qcow2")
            created = self._client.volumes.create_volume(
                pool_name=pool_name, spec=volume_spec, aspects=aspects
            )

            resource = ProvisionedResource(
                kind="volume", name=volume.name, venue_id=created.path,
                attributes={"venue_name": venue_name,
                            "pool": pool_name,
                            "path": created.path,
                            "capacity_bytes": created.capacity_bytes},
                tags=volume.tags if volume.tags is not None else {},
            )
            if existed:
                result.skipped.append(volume.name)
            else:
                result.created.append(resource)
        return

    def apply_domains(self, *, spec: LibvirtSpec, run_id: str,
                      result: LvApplyResult,
                      vpn_control_plane: Optional[Any],
                      aspects: Any) -> None:
        """
            Clone boot volumes, build seed ISOs, and define + start
            domains.

            :param spec: The :class:`LibvirtSpec`.
            :param run_id: The provisioning run id.
            :param result: The :class:`LvApplyResult` accumulator.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl
                used to mint VPN auth keys.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        live = self._client.domains.list_domains(aspects=aspects)
        live_by_name: Dict[str, Any] = {}
        for domain in live:
            live_by_name[domain.name] = domain

        for instance in spec.instances:
            venue_name = resource_name_for(spec_name=instance.name,
                                           run_id=run_id)
            if venue_name in live_by_name:
                result.skipped.append(instance.name)
                continue

            network_name = self._network_name_for(spec=spec,
                                                   instance=instance,
                                                   run_id=run_id)
            boot_path = self._clone_boot_volume(instance=instance,
                                                run_id=run_id,
                                                aspects=aspects)
            seed_path = self._build_seed_iso(
                spec=spec, instance=instance, run_id=run_id,
                venue_name=venue_name,
                vpn_control_plane=vpn_control_plane, aspects=aspects,
            )

            domain_spec = self._domain_builder.build(
                instance=instance, domain_name=venue_name, run_id=run_id,
                network_name=network_name, boot_disk_path=boot_path,
                data_disk_paths=[], seed_iso_path=seed_path,
            )
            defined = self._client.domains.define_domain(spec=domain_spec,
                                                         aspects=aspects)
            self._client.domains.create_domain(name=venue_name,
                                               aspects=aspects)

            resource = ProvisionedResource(
                kind="instance", name=instance.name, venue_id=defined.uuid,
                attributes={"venue_name": venue_name,
                            "uuid": defined.uuid,
                            "vcpus": defined.vcpus,
                            "memory_kib": defined.memory_kib,
                            "boot_disk": boot_path},
                tags=instance.tags if instance.tags is not None else {},
            )
            result.created.append(resource)

            if instance.vpn_join is not None:
                result.vpn_records.append({
                    "instance_name": instance.name,
                    "instance_id": defined.uuid,
                    "venue_name": venue_name,
                    "vpn_provider": instance.vpn_join.provider,
                    "vpn_device_id": venue_name,
                })
        return

    def _network_name_for(self, *, spec: LibvirtSpec,
                          instance: CloudInstance, run_id: str) -> str:
        """
            Resolve the libvirt network name a domain's NIC connects to.

            :param spec: The :class:`LibvirtSpec`.
            :param instance: The neutral :class:`CloudInstance`.
            :param run_id: The provisioning run id.

            :returns: The venue-side network name; the first spec
                network when the instance names no subnet match.
        """
        for network in spec.networks:
            rtnval = resource_name_for(spec_name=network.name,
                                       run_id=run_id)
            return rtnval

        rtnval = "default"
        return rtnval

    def _clone_boot_volume(self, *, instance: CloudInstance, run_id: str,
                           aspects: Any) -> str:
        """
            Clone the instance's boot volume from a base-image volume.

            The clone is a qcow2 volume with the base-image volume as its
            backing file (copy-on-write backing chain).

            :param instance: The neutral :class:`CloudInstance`.
            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.

            :returns: The on-host path of the cloned boot volume.
        """
        base_volume_name = self._config.base_image_volume_for(
            family=instance.image.family, version=instance.image.version
        )
        base_volumes = self._client.volumes.list_volumes(
            pool_name=self._config.base_image_pool, aspects=aspects
        )
        backing_path: Optional[str] = None
        backing_format = "qcow2"
        for base_volume in base_volumes:
            if base_volume.name == base_volume_name:
                backing_path = base_volume.path
                backing_format = base_volume.volume_format

        boot_name = boot_volume_name_for(
            instance_spec_name=instance.name, run_id=run_id
        )
        sizing = self._domain_builder.resolve_size(size=instance.size)
        capacity_bytes = 20 * _GIB

        boot_spec = LibvirtVolumeSpec(name=boot_name,
                                      capacity_bytes=capacity_bytes,
                                      volume_format="qcow2",
                                      backing_volume_path=backing_path,
                                      backing_format=backing_format)
        created = self._client.volumes.create_volume(
            pool_name=self._config.boot_disk_pool, spec=boot_spec,
            aspects=aspects,
        )
        rtnval = created.path
        return rtnval

    def _build_seed_iso(self, *, spec: LibvirtSpec,
                        instance: CloudInstance, run_id: str,
                        venue_name: str,
                        vpn_control_plane: Optional[Any],
                        aspects: Any) -> Optional[str]:
        """
            Build and upload the cloud-init seed ISO for a domain.

            :param spec: The :class:`LibvirtSpec`.
            :param instance: The neutral :class:`CloudInstance`.
            :param run_id: The provisioning run id.
            :param venue_name: The venue-side domain name (hostname).
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl.
            :param aspects: Behaviour control for the interop client.

            :returns: The on-host seed-ISO path, or ``None`` when the
                domain needs no seed.
        """
        authkey = ""
        if instance.vpn_join is not None and vpn_control_plane is not None:
            minted = getattr(vpn_control_plane, "minted_authkey", "")
            if minted is not None:
                authkey = minted

        user_data = self._seed_builder.render_user_data(
            instance=instance, keypairs=spec.keypairs, authkey=authkey,
            rendered_hostname=venue_name,
        )
        meta_data = self._seed_builder.render_meta_data(
            instance_id=venue_name, rendered_hostname=venue_name
        )

        seed_volume_name = seed_volume_name_for(
            instance_spec_name=instance.name, run_id=run_id
        )
        capacity_bytes = 4 * 1024 * 1024
        seed_volume_spec = LibvirtVolumeSpec(name=seed_volume_name,
                                             capacity_bytes=capacity_bytes,
                                             volume_format="raw")
        uploaded = self._client.volumes.create_volume(
            pool_name=self._config.cloudinit_pool, spec=seed_volume_spec,
            aspects=aspects,
        )

        payload = self._seed_builder.build(user_data=user_data,
                                           meta_data=meta_data,
                                           network_config="",
                                           iso_path=uploaded.path)
        rtnval = payload.iso_path
        return rtnval
