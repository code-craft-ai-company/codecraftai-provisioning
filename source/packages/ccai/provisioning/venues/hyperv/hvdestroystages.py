"""
    .. module:: hvdestroystages
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: HvDestroyStages — reverse-order teardown for the Hyper-V venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List

from ccai.provisioning.venues.hyperv.hvhostconfig import HvHostConfig
from ccai.provisioning.venues.hyperv.hvnotestranslator import (
    HvNotesTranslator
)
from ccai.provisioning.venues.hyperv.hvresolver import HvResolver


class HvDestroyStages:
    """
        Reverse-order teardown for the Hyper-V venue.

        ``destroy`` removes run-id-owned VMs (``Stop-VM -Force`` then
        ``Remove-VM``), deletes their boot and data VHDX disks, removes
        run-owned VMSwitches, and de-registers VPN devices through an
        injected ``IVPNControlPlane`` after the VMs are gone.
    """

    def __init__(self, *, client: Any, host_config: HvHostConfig,
                 resolver: HvResolver, notes: HvNotesTranslator) -> None:
        """
            Construct an HvDestroyStages.

            :param client: The HypervClient interop client.
            :param host_config: The HvHostConfig for the run.
            :param resolver: The HvResolver.
            :param notes: The HvNotesTranslator.
        """
        self._client: Any = client
        self._host_config: HvHostConfig = host_config
        self._resolver: HvResolver = resolver
        self._notes: HvNotesTranslator = notes
        return

    def destroy(self, *, spec: Any, run_id: str,
                vpn_records: List[Dict[str, Any]],
                vpn_control_plane: Any, aspects: Any,
                created_networks: List[str] = None,
                created_volumes: List[str] = None) -> None:
        """
            Tear down every run-id-owned resource in reverse apply order.

            Switches and data VHDX disks have no run-ownership marker, and
            apply reuses (never creates) a switch or disk that already exists.
            Destroy therefore removes only the switches and data disks this run
            actually created — passed in as ``created_networks`` /
            ``created_volumes`` from the apply result.  Anything not on those
            lists (a shared External switch, a pre-existing disk) is left
            untouched: under-cleanup is preferable to severing networking for
            unrelated VMs.

            :param spec: The HypervSpec (used to bound switch/disk removal).
            :param run_id: The provisioning run identifier.
            :param vpn_records: VPN device records recorded by apply.
            :param vpn_control_plane: Optional IVPNControlPlane impl.
            :param aspects: The AspectsRunner.
            :param created_networks: Names of switches this run created.
            :param created_volumes: Names of data volumes this run created.

            :returns: ``None``.
        """
        if created_networks is not None:
            owned_networks = set(created_networks)
        else:
            owned_networks = set()

        if created_volumes is not None:
            owned_volumes = set(created_volumes)
        else:
            owned_volumes = set()
        owned_vm_names: List[str] = []
        for vm in self._client.vms.list_vms(aspects=aspects):
            if self._notes.owned_by(notes_str=vm.notes, run_id=run_id):
                owned_vm_names.append(vm.name)

        for vm_name in owned_vm_names:
            self._client.vms.stop_vm(name=vm_name, force=True,
                                     aspects=aspects)
            self._client.vms.remove_vm(name=vm_name, aspects=aspects)

            boot_vhdx = self._resolver._join(
                root=self._host_config.vhd_root,
                leaf="{}-boot.vhdx".format(vm_name))
            self._client.vhdx.delete_vhdx(path=boot_vhdx, aspects=aspects)

        if spec is not None:
            for vol in spec.volumes:
                # Only delete a data disk this run created; a reused/pre-existing
                # VHDX (e.g. an existing_id-backed data disk) is left in place.
                if vol.name not in owned_volumes:
                    continue
                data_vhdx = self._resolver._join(
                    root=self._host_config.vhd_root,
                    leaf="{}-data.vhdx".format(vol.name))
                self._client.vhdx.delete_vhdx(path=data_vhdx,
                                              aspects=aspects)

        if vpn_control_plane is not None:
            for record in vpn_records:
                device_id = record.get("vpn_device_id", None)
                if device_id is None or len(str(device_id)) == 0:
                    continue
                vpn_control_plane.delete_device(device_id=device_id,
                                                aspects=aspects)

        if spec is not None:
            for net in spec.networks:
                # Only remove a switch this run created.  apply marks a
                # pre-existing switch (e.g. a shared External switch) as
                # skipped, not created, so it never appears here and is never
                # destroyed out from under unrelated VMs.
                if net.name not in owned_networks:
                    continue
                self._client.switches.remove_switch(name=net.name,
                                                    aspects=aspects)
        return
