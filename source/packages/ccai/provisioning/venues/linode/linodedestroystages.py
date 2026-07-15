"""
    .. module:: linodedestroystages
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: LinodeDestroyStages — reverse-order teardown of owned Linode
               resources with VPN control-plane device cleanup.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from ccai.provisioning.venues.vpncleanup import delete_vpn_device

from ccai.provisioning.venues.linode.linodereader import LinodeReader
from ccai.provisioning.venues.linode.linodespec import LinodeSpec


def _delete(*, obj: Any) -> None:
    """
        Best-effort delete of a Linode SDK object.

        :param obj: A Linode SDK object exposing ``delete()``.
    """
    deleter = getattr(obj, "delete", None)
    if deleter is None:
        return
    try:
        deleter()
    except Exception:
        pass
    return


class LinodeDestroyStages:
    """
        Reverse-order teardown for the Linode venue.

        Destroys DNS records → buckets → volumes → instances → SSH keys →
        firewalls → VPC subnets → VPCs.  After deleting VPN-joined instances
        it invokes ``IVPNControlPlane.delete_device`` for each recorded
        device id so the control plane does not accumulate stale nodes.
    """

    def __init__(self, *, client: Any, reader: LinodeReader,
                 vpn_control_plane: Optional[Any] = None) -> None:
        """
            Construct a LinodeDestroyStages.

            :param client: A ``linode_api4.LinodeClient``-compatible object.
            :param reader: A LinodeReader.
            :param vpn_control_plane: Optional IVPNControlPlane impl.
        """
        self._client: Any = client
        self._reader: LinodeReader = reader
        self._vpn_control_plane: Optional[Any] = vpn_control_plane
        return

    def destroy(self, *, spec: Optional[LinodeSpec], run_id: str,
                vpn_records: List[Dict[str, Any]], aspects: Any) -> None:
        """
            Destroy every owned resource in reverse dependency order.

            :param spec: The LinodeSpec, or None.
            :param run_id: The run identifier.
            :param vpn_records: VPN device records captured at apply time.
            :param aspects: Aspects.
        """
        # 1. DNS records.
        if spec is not None:
            for record in spec.dns_records:
                existing = self._reader.find_dns_record(
                    zone=record.zone, name=record.name
                )
                if existing is not None:
                    _delete(obj=existing)

        # 2. Object Storage buckets.
        if spec is not None:
            for bucket in spec.buckets:
                existing = self._reader.find_bucket(name=bucket.name)
                if existing is not None:
                    _delete(obj=existing)

        # 3. Block Storage volumes.
        for volume in self._reader.all_owned(
                collection=list(self._client.volumes())):
            try:
                detach = getattr(volume, "detach", None)
                if detach is not None:
                    detach()
            except Exception:
                pass
            _delete(obj=volume)

        # 4. Instances.
        for instance in self._reader.all_owned(
                collection=list(self._client.linode.instances())):
            _delete(obj=instance)

        # 5. VPN control-plane device cleanup.
        if self._vpn_control_plane is not None:
            for record in vpn_records:
                device_id = record.get("vpn_device_id", None)
                if device_id is None or len(str(device_id)) == 0:
                    continue
                delete_vpn_device(
                    vpn_control_plane=self._vpn_control_plane,
                    device_id=device_id, aspects=aspects)

        # 6. SSH keys.
        if spec is not None:
            for kp in spec.keypairs:
                existing = self._reader.find_sshkey(name=kp.name)
                if existing is not None:
                    _delete(obj=existing)

        # 7. Cloud Firewalls.
        for firewall in self._reader.all_owned(
                collection=list(self._client.networking.firewalls())):
            _delete(obj=firewall)

        # 8. VPC subnets + VPCs.  VPCs carry no tags, so ownership is by the
        # venue-scoped label prefix rather than tag-based all_owned.
        for vpc in self._reader.owned_vpcs():
            subnets = getattr(vpc, "subnets", None)
            if subnets is not None:
                for subnet in list(subnets):
                    _delete(obj=subnet)
            _delete(obj=vpc)
        return
