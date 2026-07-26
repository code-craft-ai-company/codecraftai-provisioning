"""
    .. module:: linodeinventory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: LinodeInventory — enumerates run-id-tagged Linode resources as
               neutral ProvisionedResource records.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import json
import os

from typing import Any, List

from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.venues.linode.linodereader import LinodeReader
from ccai.provisioning.venues.linode.linodetagtranslator import (
    LinodeTagTranslator
)


class LinodeInventory:
    """
        Enumerator of owned Linode resources for a run.

        Walks the tag-filtered listings of VPCs, firewalls, instances, and
        volumes and emits :class:`ProvisionedResource` records.
    """

    def __init__(self, *, client: Any, reader: LinodeReader,
                 translator: LinodeTagTranslator) -> None:
        """
            Construct a LinodeInventory.

            :param client: A :class:`LinodeRestClient`-compatible object.
            :param reader: A LinodeReader.
            :param translator: A LinodeTagTranslator.
        """
        self._client: Any = client
        self._reader: LinodeReader = reader
        self._translator: LinodeTagTranslator = translator
        return

    def _name_from_label(self, *, obj: Any) -> str:
        """
            Recover a resource's neutral name from its venue-scoped label.

            Linode VPCs carry NO tags, so the tag-derived name is always
            absent for them and ProvisionedResource rejects the empty
            result.  Apply names them ``codecraftai-<run_id>-<name>``, and
            the reader matches ownership on that prefix, so the neutral name
            is what follows it — the same convention, read backwards.

            :param obj: The Linode object.

            :returns: The neutral name, or an empty string when the label
                does not carry one.
        """
        label = getattr(obj, "label", None)
        if label is None:
            rtnval = ""
            return rtnval

        prefix = self._reader.owned_prefix()
        if label.startswith(prefix) is True:
            rtnval = label[len(prefix):]
            return rtnval

        rtnval = ""
        return rtnval

    def _record_for(self, *, kind: str, obj: Any) -> ProvisionedResource:
        """
            Build a ProvisionedResource for an owned Linode object.

            :param kind: The neutral resource kind.
            :param obj: The Linode object.

            :returns: A ProvisionedResource.
        """
        tags = getattr(obj, "tags", None)
        tag_list = list(tags) if tags is not None else []
        name = self._translator.resource_name_of(strings=tag_list)
        effective_name = name if name is not None else ""
        if len(effective_name) == 0:
            # Untagged kinds (VPCs) carry their name in the label instead.
            effective_name = self._name_from_label(obj=obj)
        venue_id = str(getattr(obj, "id", ""))
        rtnval = ProvisionedResource(
            kind=kind, name=effective_name, venue_id=venue_id,
            attributes={"venue_id": venue_id},
            tags=self._translator.from_linode(strings=tag_list),
        )
        return rtnval

    def list_run(self, *, aspects: Any) -> List[ProvisionedResource]:
        """
            Enumerate owned resources for the run.

            :param aspects: Aspects.

            :returns: A list of ProvisionedResource entries.
        """
        out: List[ProvisionedResource] = []

        for vpc in self._reader.owned_vpcs():
            out.append(self._record_for(kind="network", obj=vpc))

        for firewall in self._reader.all_owned(
                collection=list(self._client.networking.firewalls())):
            out.append(self._record_for(kind="sg", obj=firewall))

        for instance in self._reader.all_owned(
                collection=list(self._client.linode.instances())):
            out.append(self._record_for(kind="instance", obj=instance))

        for volume in self._reader.all_owned(
                collection=list(self._client.volumes())):
            out.append(self._record_for(kind="volume", obj=volume))

        rtnval = out
        return rtnval

    def persist(self, *, records: List[ProvisionedResource], run_id: str,
                output_root: str) -> str:
        """
            Persist the inventory under the provisioning output tree.

            Writes ``<output_root>/provisioning/<run_id>/
            linode-inventory.json``.

            :param records: The ProvisionedResource records to persist.
            :param run_id: The run identifier.
            :param output_root: The output root directory.

            :returns: The absolute path of the written file.
        """
        target_dir = os.path.join(output_root, "provisioning", run_id)
        os.makedirs(target_dir, exist_ok=True)
        target_path = os.path.join(target_dir, "linode-inventory.json")

        payload: List[Any] = []
        for record in records:
            payload.append({
                "kind": record.kind,
                "name": record.name,
                "venue_id": record.venue_id,
                "attributes": record.attributes,
                "tags": record.tags,
            })

        with open(target_path, "w", encoding="utf-8") as fileobj:
            json.dump(payload, fileobj, indent=4, sort_keys=True)

        rtnval = target_path
        return rtnval
