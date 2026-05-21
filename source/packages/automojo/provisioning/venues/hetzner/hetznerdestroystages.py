"""
    .. module:: hetznerdestroystages
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: HetznerDestroyStages — reverse-order teardown of owned state.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.provisioning.venues.vpncleanup import delete_vpn_device

from automojo.provisioning.venues.hetzner.hetznerlabeltranslator import (
    HetznerLabelTranslator
)
from automojo.provisioning.venues.hetzner.hetznerspec import HetznerSpec


def _labels_of(obj: Any) -> Dict[str, str]:
    """
        Read the ``labels`` dict off an hcloud-shaped object.

        :param obj: An hcloud resource object.

        :returns: The labels dict (empty when absent).
    """
    labels = getattr(obj, "labels", None)
    if labels is None:
        rtnval: Dict[str, str] = {}
        return rtnval
    rtnval = dict(labels)
    return rtnval


class HetznerDestroyStages:
    """
        Reverse-order teardown of every Hetzner resource owned by a run.

        Destroy order reverses apply: DNS -> Volume -> Server -> SSH Key ->
        Firewall -> Network.  VPN-joined Servers trigger an
        ``IVPNControlPlane.delete_device`` call after the Server is deleted.
    """

    def __init__(self, *, client: Any,
                 dns_client: Optional[Any] = None,
                 vpn_control_plane: Optional[Any] = None) -> None:
        """
            Construct a HetznerDestroyStages.

            :param client: An hcloud Client (or mock).
            :param dns_client: Optional Hetzner DNS API client (or mock).
            :param vpn_control_plane: Optional IVPNControlPlane impl.
        """
        self._client: Any = client
        self._dns_client: Optional[Any] = dns_client
        self._vpn_control_plane: Optional[Any] = vpn_control_plane
        return

    def destroy(self, *, spec: Optional[HetznerSpec], run_id: str,
                aspects: Any,
                vpn_records: List[Dict[str, Any]]) -> None:
        """
            Tear down every owned resource for the run in reverse order.

            :param spec: The HetznerSpec (used for DNS records).
            :param run_id: Run identifier.
            :param aspects: ProvisioningAspects.
            :param vpn_records: VPN-device records captured at apply time.
        """
        selector = HetznerLabelTranslator.label_selector(run_id=run_id)

        # 1. DNS records.
        if spec is not None and self._dns_client is not None:
            for record in spec.dns_records:
                self._dns_client.delete_records(
                    zone_name=record.zone, name=record.name)

        # 2. Volumes — detach then delete.
        for volume in self._owned(collection=self._client.volumes,
                                  selector=selector, run_id=run_id):
            self._client.volumes.detach(volume=volume)
            self._client.volumes.delete(volume=volume)

        # 3. Servers — capture ids, delete, then de-register VPN devices.
        deleted_server_ids: List[str] = []
        for server in self._owned(collection=self._client.servers,
                                  selector=selector, run_id=run_id):
            deleted_server_ids.append(str(getattr(server, "id", "")))
            self._client.servers.delete(server=server)

        if self._vpn_control_plane is not None:
            for record in vpn_records:
                device_id = record.get("vpn_device_id", None)
                if device_id is None or len(str(device_id)) == 0:
                    continue
                delete_vpn_device(
                    vpn_control_plane=self._vpn_control_plane,
                    device_id=device_id, aspects=aspects)

        # 4. SSH keys.
        for ssh_key in self._owned(collection=self._client.ssh_keys,
                                   selector=selector, run_id=run_id):
            self._client.ssh_keys.delete(ssh_key=ssh_key)

        # 5. Firewalls.
        for firewall in self._owned(collection=self._client.firewalls,
                                    selector=selector, run_id=run_id):
            self._client.firewalls.delete(firewall=firewall)

        # 6. Networks.
        for network in self._owned(collection=self._client.networks,
                                   selector=selector, run_id=run_id):
            self._client.networks.delete(network=network)

        return

    @classmethod
    def _owned(cls, *, collection: Any, selector: str,
               run_id: str) -> List[Any]:
        """
            List the run-owned objects in an hcloud resource collection.

            :param collection: An hcloud resource collection (e.g.
                                ``client.servers``).
            :param selector: The label-selector query string.
            :param run_id: Run identifier (for a defensive re-check).

            :returns: A list of owned hcloud objects.
        """
        objects = collection.get_all(label_selector=selector)
        owned: List[Any] = []
        for obj in objects:
            if HetznerLabelTranslator.belongs_to_run(
                    labels=_labels_of(obj), run_id=run_id):
                owned.append(obj)
        rtnval = owned
        return rtnval
