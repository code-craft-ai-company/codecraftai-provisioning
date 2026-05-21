"""
    .. module:: metalinventory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: MetalInventory — enumerates owned Equinix Metal resources for a
               run.

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
from automojo.provisioning.venues.equinix_metal.metalapplystages import (
    MetalApplyStages, _owned_by
)
from automojo.provisioning.venues.equinix_metal.metalclient import MetalClient
from automojo.provisioning.venues.equinix_metal.metaltagtranslator import (
    MetalTagTranslator, RESOURCE_NAME_TAG_KEY
)


class MetalInventory:
    """
        Enumerates the Equinix Metal resources owned by a run.

        Resources are matched by the owner tag-pair plus the run-id tag.
        Inventory is also persisted under
        ``.output/provisioning/<runid>/metal-inventory.json``.
    """

    def __init__(self, *, client: MetalClient,
                 stages: MetalApplyStages) -> None:
        """
            Construct a MetalInventory.

            :param client: The MetalClient.
            :param stages: The MetalApplyStages (for resource builders).
        """
        self._client: MetalClient = client
        self._stages: MetalApplyStages = stages
        return

    def list_run(self, *, run_id: str,
                 aspects: Any) -> List[ProvisionedResource]:
        """
            Enumerate every owned resource for the run.

            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: A list of ProvisionedResource records.
        """
        out: List[ProvisionedResource] = []

        for vlan in self._client.list_vlans():
            tags = vlan.get("tags", [])
            if not _owned_by(tag_strings=tags, run_id=run_id):
                continue
            name = self._name_of(tags=tags)
            if name is None:
                continue
            out.append(self._stages._vlan_resource(vlan=vlan, name=name))

        for reservation in self._client.list_ip_reservations():
            tags = reservation.get("tags", [])
            if not _owned_by(tag_strings=tags, run_id=run_id):
                continue
            name = self._name_of(tags=tags)
            if name is None:
                continue
            out.append(self._stages._ip_resource(
                reservation=reservation, name=name
            ))

        for ssh_key in self._client.list_ssh_keys():
            tags = ssh_key.get("tags", [])
            label = ssh_key.get("label", "")
            owned_label = label.startswith("automojo:{}:".format(run_id))
            if not _owned_by(tag_strings=tags, run_id=run_id) and not owned_label:
                continue
            name = self._name_of(tags=tags)
            if name is None and owned_label:
                name = label.split(":", 2)[-1]
            if name is None:
                continue
            out.append(self._stages._ssh_key_resource(
                ssh_key=ssh_key, name=name
            ))

        for device in self._client.list_devices():
            tags = device.get("tags", [])
            if not _owned_by(tag_strings=tags, run_id=run_id):
                continue
            name = self._name_of(tags=tags)
            if name is None:
                continue
            out.append(self._stages._device_resource(
                device=device, name=name
            ))

        rtnval = out
        return rtnval

    @staticmethod
    def _name_of(*, tags: Any) -> Any:
        """
            Extract the resource-name tag from a Metal tag string list.

            :param tags: Metal tag string list.

            :returns: The resource name string, or None.
        """
        flat = MetalTagTranslator.flat_dict(strings=tags)
        value = flat.get(RESOURCE_NAME_TAG_KEY, None)
        if value is None or len(value) == 0:
            rtnval = None
            return rtnval
        rtnval = value
        return rtnval

    @staticmethod
    def persist(*, run_id: str,
                resources: List[ProvisionedResource],
                output_root: str = ".output") -> str:
        """
            Persist the inventory to
            ``<output_root>/provisioning/<runid>/metal-inventory.json``.

            :param run_id: Run identifier.
            :param resources: The inventory records to persist.
            :param output_root: Root output directory.

            :returns: The absolute path of the written file.
        """
        target_dir = os.path.join(output_root, "provisioning", run_id)
        os.makedirs(target_dir, exist_ok=True)
        target_path = os.path.join(target_dir, "metal-inventory.json")

        payload: List[Any] = []
        for resource in resources:
            payload.append({
                "kind": resource.kind,
                "name": resource.name,
                "venue_id": resource.venue_id,
                "attributes": dict(resource.attributes),
                "tags": dict(resource.tags),
            })

        with open(target_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)

        rtnval = os.path.abspath(target_path)
        return rtnval
