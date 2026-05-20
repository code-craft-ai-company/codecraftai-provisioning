"""
    .. module:: hvinventory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: HvInventory — enumerates run-id-owned Hyper-V resources.

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

from automojo.provisioning.venues.hyperv.hvnotestranslator import (
    HvNotesTranslator
)


class HvInventory:
    """
        Enumerates run-id-owned Hyper-V resources.

        ``list_run`` walks ``Get-VM`` and reports each VM whose ``Notes``
        envelope carries the current run-id, attaching the
        Integration-Services / KVP-reported IP addresses.
    """

    def __init__(self, *, client: Any, notes: HvNotesTranslator) -> None:
        """
            Construct an HvInventory.

            :param client: The HypervClient interop client.
            :param notes: The HvNotesTranslator.
        """
        self._client: Any = client
        self._notes: HvNotesTranslator = notes
        return

    def list_run(self, *, run_id: str,
                 aspects: Any) -> List[ProvisionedResource]:
        """
            Enumerate run-id-owned VMs as ProvisionedResource records.

            :param run_id: The provisioning run identifier.
            :param aspects: The AspectsRunner.

            :returns: A list of ProvisionedResource entries.
        """
        out: List[ProvisionedResource] = []

        for vm in self._client.vms.list_vms(aspects=aspects):
            if not self._notes.owned_by(notes_str=vm.notes, run_id=run_id):
                continue

            envelope = self._notes.decode(notes_str=vm.notes)
            attributes: Dict[str, Any] = {
                "state": vm.state,
                "ip_addresses": list(vm.ip_addresses),
                "processor_count": vm.processor_count,
                "memory_startup_bytes": vm.memory_startup_bytes,
            }
            out.append(ProvisionedResource(
                kind="instance", name=vm.name, venue_id=vm.vm_id,
                attributes=attributes, tags=envelope.tags))

        rtnval = out
        return rtnval

    def persist(self, *, run_id: str, aspects: Any,
                output_root: str = ".output") -> str:
        """
            Write the run inventory to a JSON file under the output root.

            The file is written to
            ``<output_root>/provisioning/<runid>/hyperv-inventory.json``.

            :param run_id: The provisioning run identifier.
            :param aspects: The AspectsRunner.
            :param output_root: The base output directory.

            :returns: The path of the written inventory file.
        """
        items = self.list_run(run_id=run_id, aspects=aspects)

        run_dir = os.path.join(output_root, "provisioning", run_id)
        os.makedirs(run_dir, exist_ok=True)
        out_path = os.path.join(run_dir, "hyperv-inventory.json")

        records: List[Dict[str, Any]] = []
        for item in items:
            records.append({
                "kind": item.kind,
                "name": item.name,
                "venue_id": item.venue_id,
                "attributes": item.attributes,
                "tags": item.tags,
            })

        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump({"run_id": run_id, "resources": records}, fh, indent=2)

        rtnval = out_path
        return rtnval
