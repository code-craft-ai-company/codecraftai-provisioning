"""
    .. module:: ntxinventory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: NtxInventory — enumerates run-owned VMs for the Nutanix venue
               provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import json
import os

from typing import Any, List, Optional

from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.venues.nutanix.ntxcategorytranslator import (
    NtxCategoryTranslator
)
from ccai.provisioning.venues.nutanix.ntxnaming import run_id_short


_INVENTORY_FILENAME = "nutanix-inventory.json"


class NtxInventory:
    """
        Enumerates the Prism Central VMs owned by a provisioning run.

        Run ownership is decided by the ``codecraftai-run-id`` Category on
        each VM; the neutral tag list is recovered from the VM's
        Categories via :class:`NtxCategoryTranslator`.  Guest IPs are read
        from the Nutanix Guest Tools (NGT) NIC ip-endpoint reporting
        surfaced by :class:`NutanixVm`.
    """

    def __init__(self, *, client: Any,
                 config: Any = None,
                 output_root: str = ".output",
                 category_translator: Optional[
                     NtxCategoryTranslator] = None) -> None:
        """
            Construct an NtxInventory.

            :param client: The Nutanix interop client.
            :param config: The :class:`NutanixVenueConfig` (retained for
                interface uniformity).
            :param output_root: The output root directory.
            :param category_translator: Optional
                :class:`NtxCategoryTranslator`.
        """
        self._client = client
        self._config = config
        self._output_root = output_root
        if category_translator is not None:
            self._category_translator: NtxCategoryTranslator = (
                category_translator
            )
        else:
            self._category_translator = NtxCategoryTranslator(client=client)
        return

    def list_run(self, *, run_id: str,
                 aspects: Any) -> List[ProvisionedResource]:
        """
            Enumerate every run-id-categoried VM.

            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.

            :returns: A list of :class:`ProvisionedResource` records.
        """
        suffix = "-" + run_id_short(run_id=run_id)

        out: List[ProvisionedResource] = []

        for vm in self._client.vms.list(aspects=aspects):
            embedded_run_id = self._category_translator.run_id_of(vm=vm)

            if embedded_run_id is not None and len(embedded_run_id) > 0:
                owned = embedded_run_id == run_id
            else:
                owned = vm.name.endswith(suffix)
            if not owned:
                continue

            tags = self._category_translator.read(vm=vm)
            ip_address = ""
            if vm.ip_addresses is not None and len(vm.ip_addresses) > 0:
                ip_address = vm.ip_addresses[0]

            out.append(ProvisionedResource(
                kind="instance", name=vm.name, venue_id=vm.uuid,
                attributes={"uuid": vm.uuid,
                            "power_state": vm.power_state,
                            "num_vcpus": vm.num_vcpus,
                            "memory_mib": vm.memory_mib,
                            "cluster_uuid": vm.cluster_uuid,
                            "ip": ip_address},
                tags=tags,
            ))

        rtnval = out
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
                "tags": dict(resource.tags),
            })

        with open(path, "w", encoding="utf-8") as fh:
            json.dump(document, fh, indent=2, sort_keys=True)

        rtnval = path
        return rtnval
