"""
    .. module:: hetznerinventory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: HetznerInventory — enumerate run-owned Hetzner resources.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import json
import os

from typing import Any, Dict, List

from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.venues.hetzner.hetznerlabeltranslator import (
    HetznerLabelTranslator, RESOURCE_NAME_LABEL_KEY
)


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


def _id_of(obj: Any) -> str:
    """
        Read the ``id`` attribute off an hcloud-shaped object as a string.

        :param obj: An hcloud resource object.

        :returns: The string id (empty when absent).
    """
    raw_id = getattr(obj, "id", None)
    if raw_id is None:
        rtnval = ""
        return rtnval
    rtnval = str(raw_id)
    return rtnval


class HetznerInventory:
    """
        Enumerator producing :class:`ProvisionedResource` records for every
        run-id-labelled Hetzner resource.
    """

    def __init__(self, *, client: Any) -> None:
        """
            Construct a HetznerInventory.

            :param client: An hcloud Client (or mock).
        """
        self._client: Any = client
        return

    def list_run(self, *, run_id: str,
                 aspects: Any) -> List[ProvisionedResource]:
        """
            Enumerate every run-owned Hetzner resource.

            :param run_id: Run identifier.
            :param aspects: ProvisioningAspects.

            :returns: A list of ProvisionedResource records.
        """
        selector = HetznerLabelTranslator.label_selector(run_id=run_id)
        out: List[ProvisionedResource] = []

        kind_collections = [
            ("network", self._client.networks),
            ("security_group", self._client.firewalls),
            ("keypair", self._client.ssh_keys),
            ("instance", self._client.servers),
            ("volume", self._client.volumes),
        ]

        for kind, collection in kind_collections:
            objects = collection.get_all(label_selector=selector)
            for obj in objects:
                labels = _labels_of(obj)
                if not HetznerLabelTranslator.belongs_to_run(
                        labels=labels, run_id=run_id):
                    continue
                resource_name = labels.get(RESOURCE_NAME_LABEL_KEY,
                                           getattr(obj, "name", _id_of(obj)))
                out.append(ProvisionedResource(
                    kind=kind, name=resource_name, venue_id=_id_of(obj),
                    attributes={"hetzner_id": _id_of(obj)},
                    tags=HetznerLabelTranslator.from_hetzner(labels=labels)))

        rtnval = out
        return rtnval

    @classmethod
    def persist(cls, *, run_id: str,
                resources: List[ProvisionedResource],
                output_root: str = ".output") -> str:
        """
            Persist an inventory to ``<root>/provisioning/<runid>/
            hetzner-inventory.json``.

            :param run_id: Run identifier.
            :param resources: The ProvisionedResource records to persist.
            :param output_root: The output-root directory.

            :returns: The absolute path the inventory was written to.
        """
        run_dir = os.path.join(output_root, "provisioning", run_id)
        os.makedirs(run_dir, exist_ok=True)
        inventory_path = os.path.join(run_dir, "hetzner-inventory.json")

        payload: List[Dict[str, Any]] = []
        for resource in resources:
            payload.append({
                "kind": resource.kind,
                "name": resource.name,
                "venue_id": resource.venue_id,
                "attributes": dict(resource.attributes),
                "tags": dict(resource.tags),
            })

        with open(inventory_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)

        rtnval = os.path.abspath(inventory_path)
        return rtnval
