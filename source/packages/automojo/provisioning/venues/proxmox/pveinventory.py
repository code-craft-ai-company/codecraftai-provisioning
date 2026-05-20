"""
    .. module:: pveinventory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: PveInventory — enumerates run-owned VMs across every cluster
               node for the Proxmox VE venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import json
import os

from typing import Any, List

from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.venues.proxmox.pvenaming import (
    OWNER_TAG, RUN_ID_TAG_PREFIX, has_run_id_tag
)
from automojo.provisioning.venues.proxmox.pvetagtranslator import (
    PveTagTranslator
)


_INVENTORY_FILENAME = "pve-inventory.json"


class PveInventory:
    """
        Enumerates the Proxmox VE resources owned by a provisioning run.

        Run ownership is decided by the ``automojo-run-id`` Proxmox tag;
        the neutral tag list is recovered from the VM tag string with the
        venue-internal owner / run-id tags filtered out.
    """

    def __init__(self, *, client: Any,
                 output_root: str = ".output") -> None:
        """
            Construct a PveInventory.

            :param client: The Proxmox interop client.
            :param output_root: The output root directory.
        """
        self._client = client
        self._output_root = output_root
        return

    def list_run(self, *, run_id: str,
                 aspects: Any) -> List[ProvisionedResource]:
        """
            Enumerate every run-owned VM across every cluster node.

            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.

            :returns: A list of :class:`ProvisionedResource` records.
        """
        out: List[ProvisionedResource] = []

        for node in self._client.nodes.list(aspects=aspects):
            for vm in self._client.qemu.list_vms(node_name=node.name,
                                                 aspects=aspects):
                if has_run_id_tag(tags=vm.tags, run_id=run_id) is not True:
                    continue
                neutral_tags = self._neutral_tags(pve_tags=vm.tags)
                out.append(ProvisionedResource(
                    kind="instance",
                    name=vm.name if vm.name is not None else str(vm.vmid),
                    venue_id=str(vm.vmid),
                    attributes={"vmid": vm.vmid, "node": node.name,
                                "status": vm.status},
                    tags=neutral_tags,
                ))

        rtnval = out
        return rtnval

    @staticmethod
    def _neutral_tags(*, pve_tags: List[str]) -> List[dict]:
        """
            Recover the neutral tag list from a Proxmox tag list.

            The venue-internal owner and run-id tags are filtered out so
            inventory reports only the user-supplied neutral tags.

            :param pve_tags: The raw Proxmox tag list.

            :returns: A list of single-entry neutral tag dicts.
        """
        user_tags: List[str] = []
        for token in pve_tags:
            if token == OWNER_TAG:
                continue
            if token.startswith(RUN_ID_TAG_PREFIX):
                continue
            user_tags.append(token)
        rtnval = PveTagTranslator.from_pve(pve_tags=user_tags)
        return rtnval

    def persist(self, *, run_id: str,
                resources: List[ProvisionedResource]) -> str:
        """
            Persist an inventory snapshot to the run output directory.

            :param run_id: The provisioning run id.
            :param resources: The resources to persist.

            :returns: The path the inventory snapshot was written to.
        """
        directory = os.path.join(self._output_root, "provisioning", run_id)
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

        path = os.path.join(directory, _INVENTORY_FILENAME)
        document = []
        for resource in resources:
            document.append({
                "kind": resource.kind,
                "name": resource.name,
                "venue_id": resource.venue_id,
                "attributes": dict(resource.attributes),
                "tags": [dict(tag) for tag in resource.tags],
            })

        with open(path, "w", encoding="utf-8") as fh:
            json.dump(document, fh, indent=2, sort_keys=True)

        rtnval = path
        return rtnval
