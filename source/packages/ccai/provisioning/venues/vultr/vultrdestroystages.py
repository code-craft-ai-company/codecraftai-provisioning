"""
    .. module:: vultrdestroystages
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: VultrDestroyStages — reverse-order owned-resource teardown.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List

from ccai.provisioning.venues.vultr.vultrclient import VultrClient
from ccai.provisioning.venues.vultr.vultrresources import list_owned_raw


class VultrDestroyStages:
    """
        Reverse-order teardown of every owned Vultr resource for a run.

        Destroy walks DNS → Object Storage → Block Storage → Instances →
        SSH Keys → Firewall Groups → VPCs, the inverse of the apply order.
        Instance VPN device cleanup is delegated to the provisioner.
    """

    def __init__(self, *, client: VultrClient) -> None:
        """
            Construct a VultrDestroyStages.

            :param client: A VultrClient.
        """
        self._client: VultrClient = client
        return

    def destroy(self, *, spec: Any, run_id: str) -> List[Dict[str, Any]]:
        """
            Destroy every owned resource in reverse apply order.

            :param spec: The VultrSpec (may be None).
            :param run_id: The provisioning run identifier.

            :returns: A list of VPN device records harvested from deleted
                      instances so the caller can de-register them.
        """
        # 1. DNS records — undo the upserts declared in the spec.
        if spec is not None:
            for record in spec.dns_records:
                self._destroy_dns_record(record=record)

        # 2. Object Storage subscriptions.
        self._destroy_collection(path="/object-storage",
                                 collection_key="object_storages",
                                 run_id=run_id)

        # 3. Block Storage — detach then delete.
        blocks = list_owned_raw(client=self._client, path="/blocks",
                                collection_key="blocks", run_id=run_id)
        for block in blocks:
            block_id = block.get("id", "")
            try:
                self._client.post(
                    path="/blocks/{}/detach".format(block_id),
                    json_body={},
                )
            except Exception:
                # Best-effort detach; the block storage volume may already be
                # detached, and the delete below is attempted either way.
                pass
            try:
                self._client.delete(path="/blocks/{}".format(block_id))
            except Exception:
                # Best-effort teardown; a failed delete must not stop the remaining
                # resources of the run from being torn down.
                pass

        # 4. Instances — capture VPN device records first.
        vpn_records: List[Dict[str, Any]] = []
        instances = list_owned_raw(client=self._client, path="/instances",
                                   collection_key="instances", run_id=run_id)
        for instance in instances:
            instance_id = instance.get("id", "")
            vpn_records.append({
                "instance_id": instance_id,
                "instance_name": instance.get("label", ""),
                "vpn_device_id": None,
            })
            try:
                self._client.delete(
                    path="/instances/{}".format(instance_id)
                )
            except Exception:
                # Best-effort teardown; a failed delete must not stop the remaining
                # resources of the run from being torn down.
                pass

        # 5. SSH keys.
        self._destroy_collection(path="/ssh-keys",
                                 collection_key="ssh_keys", run_id=run_id)

        # 6. Firewall Groups.
        self._destroy_collection(path="/firewalls",
                                 collection_key="firewall_groups",
                                 run_id=run_id)

        # 7. VPCs.
        self._destroy_collection(path="/vpc2", collection_key="vpcs",
                                 run_id=run_id)

        rtnval = vpn_records
        return rtnval

    def _destroy_collection(self, *, path: str, collection_key: str,
                            run_id: str) -> None:
        """
            Delete every owned entry at a Vultr list endpoint.

            :param path: The list endpoint path.
            :param collection_key: The list collection key.
            :param run_id: The provisioning run identifier.
        """
        entries = list_owned_raw(client=self._client, path=path,
                                 collection_key=collection_key,
                                 run_id=run_id)
        for entry in entries:
            entry_id = entry.get("id", "")
            try:
                self._client.delete(path="{}/{}".format(path, entry_id))
            except Exception:
                # Best-effort teardown; a failed delete must not stop the remaining
                # resources of the run from being torn down.
                pass
        return

    def _destroy_dns_record(self, *, record: Any) -> None:
        """
            Delete the DNS records matching a declared CloudDnsRecord.

            :param record: The CloudDnsRecord.
        """
        try:
            response = self._client.list_all(
                path="/domains/{}/records".format(record.zone),
                collection_key="records",
            )
        except Exception:
            return

        for entry in response:
            entry_name = entry.get("name", "")
            entry_type = entry.get("type", "")
            if entry_name == record.name and entry_type == record.record_type:
                entry_id = entry.get("id", "")
                try:
                    self._client.delete(
                        path="/domains/{}/records/{}".format(
                            record.zone, entry_id
                        )
                    )
                except Exception:
                    # Best-effort teardown of the DNS record; a record that cannot be deleted
                    # must not stop the remaining resources of the run from being torn down.
                    pass
        return
