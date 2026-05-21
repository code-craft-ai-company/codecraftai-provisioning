"""
    .. module:: lvdestroystages
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: LvDestroyStages — reverses apply for the libvirt venue
               provisioner: destroys + undefines domains, deletes cloned
               volumes, undefines networks, and cleans up VPN devices.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.provisioning.venues.vpncleanup import delete_vpn_device

from automojo.provisioning.venues.libvirt.libvirtspec import LibvirtSpec
from automojo.provisioning.venues.libvirt.libvirtvenueconfig import (
    LibvirtVenueConfig
)
from automojo.provisioning.venues.libvirt.lvnaming import (
    boot_volume_name_for, resource_name_for, run_id_short,
    seed_volume_name_for
)


class LvDestroyStages:
    """
        The libvirt destroy stages.

        Destroy reverses apply: each run-owned domain is destroyed (force
        power-off) then undefined; the domain's cloned boot volume and
        cloud-init seed volume are deleted; each run-owned network is
        stopped and undefined; and — for any VPN-joined domain —
        ``IVPNControlPlane.delete_device`` is invoked so the VPN control
        plane does not accumulate stale device registrations.  Deleting
        an absent resource is a no-op, so destroy is idempotent.
    """

    def __init__(self, *, client: Any,
                 config: LibvirtVenueConfig) -> None:
        """
            Construct an LvDestroyStages.

            :param client: The libvirt interop client.
            :param config: The :class:`LibvirtVenueConfig`.
        """
        self._client = client
        self._config = config
        return

    def destroy(self, *, spec: Optional[LibvirtSpec], run_id: str,
                vpn_records: List[Dict[str, Any]],
                vpn_control_plane: Optional[Any], aspects: Any) -> None:
        """
            Tear down every run-owned resource in reverse order.

            :param spec: The :class:`LibvirtSpec`, or ``None`` when
                destroying from a persisted run id.
            :param run_id: The provisioning run id.
            :param vpn_records: The VPN-device records captured at apply.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        self._destroy_domains(spec=spec, run_id=run_id, aspects=aspects)
        self._destroy_volumes(spec=spec, run_id=run_id, aspects=aspects)
        self._destroy_networks(spec=spec, run_id=run_id, aspects=aspects)
        self._cleanup_vpn_devices(vpn_records=vpn_records,
                                  vpn_control_plane=vpn_control_plane,
                                  aspects=aspects)
        return

    def _owned_suffix(self, *, run_id: str) -> str:
        """
            Return the venue-name suffix marking run ownership.

            :param run_id: The provisioning run id.

            :returns: The ``-<run-id-short>`` ownership suffix.
        """
        rtnval = "-" + run_id_short(run_id=run_id)
        return rtnval

    def _destroy_domains(self, *, spec: Optional[LibvirtSpec],
                         run_id: str, aspects: Any) -> None:
        """
            Destroy then undefine every run-owned domain.

            :param spec: The :class:`LibvirtSpec` or ``None``.
            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        suffix = self._owned_suffix(run_id=run_id)
        owned_names = self._owned_domain_names(spec=spec, run_id=run_id)

        live = self._client.domains.list_domains(aspects=aspects)
        for domain in live:
            if spec is not None:
                owned = domain.name in owned_names
            else:
                owned = domain.name.endswith(suffix)
            if not owned:
                continue
            self._client.domains.destroy_domain(name=domain.name,
                                                aspects=aspects)
            self._client.domains.undefine_domain(name=domain.name,
                                                 aspects=aspects)
        return

    def _destroy_volumes(self, *, spec: Optional[LibvirtSpec],
                         run_id: str, aspects: Any) -> None:
        """
            Delete the run's cloned boot volumes and seed volumes.

            :param spec: The :class:`LibvirtSpec` or ``None``.
            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        if spec is None:
            self._destroy_volumes_by_suffix(run_id=run_id, aspects=aspects)
            return

        for instance in spec.instances:
            boot_name = boot_volume_name_for(
                instance_spec_name=instance.name, run_id=run_id
            )
            self._client.volumes.delete_volume(
                pool_name=self._config.boot_disk_pool, name=boot_name,
                aspects=aspects,
            )
            seed_name = seed_volume_name_for(
                instance_spec_name=instance.name, run_id=run_id
            )
            self._client.volumes.delete_volume(
                pool_name=self._config.cloudinit_pool, name=seed_name,
                aspects=aspects,
            )

        for volume in spec.volumes:
            venue_name = resource_name_for(spec_name=volume.name,
                                           run_id=run_id)
            self._client.volumes.delete_volume(
                pool_name=self._config.boot_disk_pool, name=venue_name,
                aspects=aspects,
            )
        return

    def _destroy_volumes_by_suffix(self, *, run_id: str,
                                   aspects: Any) -> None:
        """
            Delete every run-owned volume across the venue pools.

            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        suffix = self._owned_suffix(run_id=run_id)
        pools = {self._config.boot_disk_pool, self._config.cloudinit_pool}
        for pool_name in pools:
            volumes = self._client.volumes.list_volumes(
                pool_name=pool_name, aspects=aspects
            )
            for volume in volumes:
                owned = (volume.name.endswith(suffix)
                         or volume.name.endswith(suffix + "-boot.qcow2")
                         or volume.name.endswith(suffix + "-seed.iso"))
                if not owned:
                    continue
                self._client.volumes.delete_volume(
                    pool_name=pool_name, name=volume.name, aspects=aspects
                )
        return

    def _destroy_networks(self, *, spec: Optional[LibvirtSpec],
                          run_id: str, aspects: Any) -> None:
        """
            Stop then undefine every run-owned network.

            :param spec: The :class:`LibvirtSpec` or ``None``.
            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        suffix = self._owned_suffix(run_id=run_id)
        owned_names: List[str] = []
        if spec is not None:
            for network in spec.networks:
                owned_names.append(resource_name_for(
                    spec_name=network.name, run_id=run_id
                ))

        live = self._client.networks.list_networks(aspects=aspects)
        for network in live:
            if spec is not None:
                owned = network.name in owned_names
            else:
                owned = network.name.endswith(suffix)
            if not owned:
                continue
            self._client.networks.stop_network(name=network.name,
                                               aspects=aspects)
            self._client.networks.undefine_network(name=network.name,
                                                   aspects=aspects)
        return

    def _cleanup_vpn_devices(self, *, vpn_records: List[Dict[str, Any]],
                             vpn_control_plane: Optional[Any],
                             aspects: Any) -> None:
        """
            De-register VPN devices for VPN-joined domains.

            :param vpn_records: The VPN-device records captured at apply.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        if vpn_control_plane is None:
            return

        for record in vpn_records:
            device_id = record.get("vpn_device_id", None)
            if device_id is None or len(str(device_id)) == 0:
                continue
            delete_vpn_device(vpn_control_plane=vpn_control_plane,
                              device_id=device_id, aspects=aspects)
        return

    def _owned_domain_names(self, *, spec: Optional[LibvirtSpec],
                            run_id: str) -> List[str]:
        """
            Compute the venue-side domain names owned by the run.

            :param spec: The :class:`LibvirtSpec` or ``None``.
            :param run_id: The provisioning run id.

            :returns: The list of run-owned venue-side domain names.
        """
        names: List[str] = []
        if spec is None:
            rtnval = names
            return rtnval

        for instance in spec.instances:
            names.append(resource_name_for(spec_name=instance.name,
                                           run_id=run_id))
        rtnval = names
        return rtnval
