"""
    .. module:: pvedestroystages
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: PveDestroyStages — stops and deletes run-owned VMs, removes
               created bridges, and de-registers VPN devices for the
               Proxmox VE venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.provisioning.venues.proxmox.pvenaming import has_run_id_tag
from automojo.provisioning.venues.proxmox.proxmoxspec import ProxmoxSpec


class PveDestroyStages:
    """
        The Proxmox VE destroy stages.

        Destroy reverses apply: it stops then deletes every VM carrying the
        run-id tag across every cluster node, and — for any VPN-joined VM —
        invokes ``IVPNControlPlane.delete_device`` so the VPN control plane
        does not accumulate stale device registrations.
    """

    def __init__(self, *, client: Any) -> None:
        """
            Construct a PveDestroyStages.

            :param client: The Proxmox interop client.
        """
        self._client = client
        return

    def destroy(self, *, spec: Optional[ProxmoxSpec], run_id: str,
                vpn_records: List[Dict[str, Any]],
                vpn_control_plane: Optional[Any], aspects: Any) -> None:
        """
            Stop and delete run-owned VMs and clean up VPN devices.

            :param spec: The :class:`ProxmoxSpec`, or ``None`` when
                destroying from a persisted run id.
            :param run_id: The provisioning run id.
            :param vpn_records: The VPN-device records captured at apply.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        # `spec` is retained for interface uniformity; destroy locates
        # owned VMs by the run-id tag, not by the spec contents.
        _ = spec

        for node in self._client.nodes.list(aspects=aspects):
            vms = self._client.qemu.list_vms(node_name=node.name,
                                             aspects=aspects)
            for vm in vms:
                if has_run_id_tag(tags=vm.tags, run_id=run_id) is not True:
                    continue
                self._destroy_vm(node_name=node.name, vmid=vm.vmid,
                                 aspects=aspects)

        if vpn_control_plane is not None:
            for record in vpn_records:
                device_id = record.get("vpn_device_id", None)
                if device_id is None or len(str(device_id)) == 0:
                    continue
                vpn_control_plane.delete_device(device_id=device_id,
                                                aspects=aspects)
        return

    def _destroy_vm(self, *, node_name: str, vmid: int,
                    aspects: Any) -> None:
        """
            Stop then delete a single VM.

            :param node_name: The node hosting the VM.
            :param vmid: The numeric VM identifier.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        stop_handle = self._client.qemu.stop_vm(node_name=node_name,
                                                vmid=vmid, aspects=aspects)
        if stop_handle is not None:
            stop_handle.wait(aspects=aspects, raise_on_failure=False)

        destroy_handle = self._client.qemu.destroy_vm(node_name=node_name,
                                                      vmid=vmid,
                                                      aspects=aspects)
        if destroy_handle is not None:
            destroy_handle.wait(aspects=aspects, raise_on_failure=False)
        return
