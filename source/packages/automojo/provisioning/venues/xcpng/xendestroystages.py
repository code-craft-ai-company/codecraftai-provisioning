"""
    .. module:: xendestroystages
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: XenDestroyStages — shuts down and destroys run-owned VMs (with
        their VDIs) and de-registers VPN devices for the XCP-ng venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.provisioning.venues.vpncleanup import delete_vpn_device

from automojo.provisioning.venues.xcpng.xentagtranslator import (
    XenTagTranslator
)
from automojo.provisioning.venues.xcpng.xcpngspec import XcpngSpec


class XenDestroyStages:
    """
        The XCP-ng destroy stages.

        Destroy reverses apply: it cleanly shuts down every VM whose
        ``other_config`` carries the run id, destroys those VMs together with
        the additional VDIs the run attached, and — for any VPN-joined VM —
        invokes ``IVPNControlPlane.delete_device`` so the VPN control plane
        does not accumulate stale device registrations.  XCP-ng networks are
        pool-administrator-managed; the venue never created one, so destroy
        never removes one.
    """

    def __init__(self, *, client: Any) -> None:
        """
            Construct an XenDestroyStages.

            :param client: The :class:`XenClient`.
        """
        self._client = client
        self._translator = XenTagTranslator()
        return

    def destroy(self, *, spec: Optional[XcpngSpec], run_id: str,
                vpn_records: List[Dict[str, Any]],
                vpn_control_plane: Optional[Any], aspects: Any) -> None:
        """
            Tear down every run-owned VM and clean up VPN devices.

            :param spec: The :class:`XcpngSpec`, or None when destroying
                         from a persisted run id.
            :param run_id: The provisioning run id.
            :param vpn_records: The VPN-device records captured at apply.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl.
            :param aspects: Behaviour control for the interop client.
        """
        _ = spec
        owned_vms = self._owned_vms(run_id=run_id, aspects=aspects)

        for vm in owned_vms:
            self._teardown_vm(vm=vm, aspects=aspects)

        self._cleanup_vpn_devices(vpn_records=vpn_records,
                                  vpn_control_plane=vpn_control_plane,
                                  aspects=aspects)
        return

    def _owned_vms(self, *, run_id: str, aspects: Any) -> List[Any]:
        """
            Enumerate the VMs whose ``other_config`` carries the run id.

            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.

            :returns: The list of run-owned XenVm records.
        """
        owned: List[Any] = []
        for vm in self._client.Vms.list(aspects=aspects):
            if self._translator.run_id_of(vm_record=vm) == run_id:
                owned.append(vm)
        rtnval = owned
        return rtnval

    def _teardown_vm(self, *, vm: Any, aspects: Any) -> None:
        """
            Clean-shutdown then destroy a single VM and its run VDIs.

            :param vm: The XenVm record to tear down.
            :param aspects: Behaviour control for the interop client.
        """
        if vm.power_state != "Halted":
            shutdown_handle = self._client.Vms.clean_shutdown(
                vm_uuid=vm.uuid, aspects=aspects)
            if shutdown_handle is not None:
                shutdown_handle.wait(aspects=aspects)

        vdi_uuids = self._run_vdi_uuids(vm_uuid=vm.uuid, aspects=aspects)

        self._client.Vms.destroy(vm_uuid=vm.uuid, aspects=aspects)

        for vdi_uuid in vdi_uuids:
            self._client.Vdi.delete(vdi_uuid=vdi_uuid, aspects=aspects)
        return

    def _run_vdi_uuids(self, *, vm_uuid: str, aspects: Any) -> List[str]:
        """
            Return the VDI uuids attached to a VM through non-boot VBDs.

            :param vm_uuid: The VM uuid.
            :param aspects: Behaviour control for the interop client.

            :returns: The list of attached VDI uuids.
        """
        out: List[str] = []
        for vbd in self._client.Vbds.list(vm_uuid=vm_uuid, aspects=aspects):
            if vbd.bootable is True:
                continue
            if vbd.vdi_uuid is not None and len(vbd.vdi_uuid) > 0:
                out.append(vbd.vdi_uuid)
        rtnval = out
        return rtnval

    @staticmethod
    def _cleanup_vpn_devices(*, vpn_records: List[Dict[str, Any]],
                             vpn_control_plane: Optional[Any],
                             aspects: Any) -> None:
        """
            De-register VPN devices for the run's VPN-joined VMs.

            :param vpn_records: The VPN-device records captured at apply.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl.
            :param aspects: Behaviour control for the interop client.
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
