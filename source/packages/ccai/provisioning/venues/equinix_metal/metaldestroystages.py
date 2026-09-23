"""
    .. module:: metaldestroystages
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: MetalDestroyStages — reverse-order teardown for the Equinix
               Metal venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List

from ccai.provisioning.venues.equinix_metal.metalapplystages import (
    _owned_by
)
from ccai.provisioning.venues.equinix_metal.metalclient import MetalClient
from ccai.provisioning.venues.equinix_metal.metaltagtranslator import (
    MetalTagTranslator, VPN_PROVIDER_TAG_KEY, VPN_DEVICE_ID_TAG_KEY
)


class MetalDestroyStages:
    """
        Reverse-order teardown for the Equinix Metal venue.

        Destroy reverses apply: Devices → IP Reservations → VLANs.  SSH keys
        are project-level and are torn down after the devices that reference
        them.  When a destroyed device carried ``vpn_join`` the destroy stage
        surfaces its VPN device records so the provisioner can de-register
        the device from the VPN control plane.
    """

    def __init__(self, *, client: MetalClient) -> None:
        """
            Construct a MetalDestroyStages.

            :param client: The MetalClient.
        """
        self._client: MetalClient = client
        return

    def destroy(self, *, run_id: str,
                aspects: Any) -> List[Dict[str, Any]]:
        """
            Tear down every owned resource for the run in reverse order.

            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: A list of VPN device records for destroyed devices,
                      each ``{"device_id", "vpn_provider", "vpn_device_id"}``.
        """
        vpn_records: List[Dict[str, Any]] = []

        # 1. Devices first.
        for device in self._client.list_devices():
            tags = device.get("tags", [])
            if not _owned_by(tag_strings=tags, run_id=run_id):
                continue
            device_id = str(device.get("id", ""))
            flat = MetalTagTranslator.flat_dict(strings=tags)
            provider = flat.get(VPN_PROVIDER_TAG_KEY, None)
            if provider is not None:
                vpn_records.append({
                    "device_id": device_id,
                    "vpn_provider": provider,
                    "vpn_device_id": flat.get(VPN_DEVICE_ID_TAG_KEY, None),
                })
            try:
                self._client.delete_device(device_id=device_id)
            except Exception:
                # Best-effort teardown; a failed delete must not stop the remaining
                # resources of the run from being torn down.
                pass

        # 2. SSH keys.
        for ssh_key in self._client.list_ssh_keys():
            label = ssh_key.get("label", "")
            tags = ssh_key.get("tags", [])
            owned_label = label.startswith("ccai:{}:".format(run_id))
            owned_tag = _owned_by(tag_strings=tags, run_id=run_id)
            if not owned_label and not owned_tag:
                continue
            try:
                self._client.delete_ssh_key(
                    ssh_key_id=str(ssh_key.get("id", ""))
                )
            except Exception:
                # Best-effort teardown; a failed delete must not stop the remaining
                # resources of the run from being torn down.
                pass

        # 3. IP reservations.
        for reservation in self._client.list_ip_reservations():
            tags = reservation.get("tags", [])
            if not _owned_by(tag_strings=tags, run_id=run_id):
                continue
            try:
                self._client.delete_ip_reservation(
                    reservation_id=str(reservation.get("id", ""))
                )
            except Exception:
                # Best-effort teardown; a failed delete must not stop the remaining
                # resources of the run from being torn down.
                pass

        # 4. VLANs.
        for vlan in self._client.list_vlans():
            tags = vlan.get("tags", [])
            if not _owned_by(tag_strings=tags, run_id=run_id):
                continue
            try:
                self._client.delete_vlan(vlan_id=str(vlan.get("id", "")))
            except Exception:
                # Best-effort teardown; a failed delete must not stop the remaining
                # resources of the run from being torn down.
                pass

        rtnval = vpn_records
        return rtnval
