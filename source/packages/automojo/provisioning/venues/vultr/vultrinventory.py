"""
    .. module:: vultrinventory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: VultrInventory — enumerate owned Vultr resources for a run.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import json
import os

from typing import Any, Dict, List

from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.venues.vultr.vultrclient import VultrClient
from automojo.provisioning.venues.vultr.vultrresources import (
    list_owned_raw, neutral_tags_of
)
from automojo.provisioning.venues.vultr.vultrtagtranslator import (
    RESOURCE_NAME_TAG_KEY
)


_INVENTORY_ENDPOINTS = [
    ("network", "/vpc2", "vpcs"),
    ("sg", "/firewalls", "firewall_groups"),
    ("keypair", "/ssh-keys", "ssh_keys"),
    ("instance", "/instances", "instances"),
    ("volume", "/blocks", "blocks"),
    ("bucket", "/object-storage", "object_storages"),
]


class VultrInventory:
    """
        Enumerates owned Vultr resources for a provisioning run.

        ``list_run`` walks each run-id-tagged list endpoint and produces a
        :class:`ProvisionedResource` per entry.  ``persist`` writes the
        inventory to ``.output/provisioning/<runid>/vultr-inventory.json``.
    """

    def __init__(self, *, client: VultrClient) -> None:
        """
            Construct a VultrInventory.

            :param client: A VultrClient.
        """
        self._client: VultrClient = client
        return

    def list_run(self, *, run_id: str) -> List[ProvisionedResource]:
        """
            Enumerate every owned resource for the run.

            :param run_id: The provisioning run identifier.

            :returns: A list of ProvisionedResource records.
        """
        out: List[ProvisionedResource] = []
        for kind, path, collection_key in _INVENTORY_ENDPOINTS:
            entries = list_owned_raw(client=self._client, path=path,
                                     collection_key=collection_key,
                                     run_id=run_id)
            for entry in entries:
                resource = self._to_resource(kind=kind, entry=entry)
                out.append(resource)
        rtnval = out
        return rtnval

    def persist(self, *, run_id: str,
                resources: List[ProvisionedResource]) -> str:
        """
            Persist the inventory under the run-scoped output directory.

            :param run_id: The provisioning run identifier.
            :param resources: The ProvisionedResource records to persist.

            :returns: The path of the written inventory file.
        """
        out_dir = os.path.join(".output", "provisioning", run_id)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "vultr-inventory.json")

        payload: List[Dict[str, Any]] = []
        for resource in resources:
            payload.append({
                "kind": resource.kind,
                "name": resource.name,
                "venue_id": resource.venue_id,
                "attributes": resource.attributes,
                "tags": resource.tags,
            })

        with open(out_path, "w", encoding="utf-8") as out_file:
            json.dump({"run_id": run_id, "resources": payload}, out_file,
                      indent=4, sort_keys=True)

        rtnval = out_path
        return rtnval

    @staticmethod
    def _to_resource(*, kind: str, entry: Dict[str, Any]
                     ) -> ProvisionedResource:
        """
            Convert a Vultr API entry to a ProvisionedResource.

            :param kind: The neutral resource kind string.
            :param entry: The Vultr API resource dict.

            :returns: A ProvisionedResource.
        """
        neutral_tags = neutral_tags_of(entry=entry)
        name = entry.get("label", "")
        if RESOURCE_NAME_TAG_KEY in neutral_tags:
            name = neutral_tags[RESOURCE_NAME_TAG_KEY]

        venue_id = str(entry.get("id", ""))
        rtnval = ProvisionedResource(
            kind=kind, name=name, venue_id=venue_id,
            attributes={"id": venue_id}, tags=neutral_tags,
        )
        return rtnval
