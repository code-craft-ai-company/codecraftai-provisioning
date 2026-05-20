"""
    .. module:: xeninventory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: XenInventory — enumerates run-owned VMs across an XCP-ng Pool
        for the venue provisioner.

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

from automojo.provisioning.venues.xcpng.xentagtranslator import (
    XenTagTranslator
)


_INVENTORY_FILENAME = "xcpng-inventory.json"


class XenInventory:
    """
        Enumerates the XCP-ng resources owned by a provisioning run.

        Run ownership is decided by the ``VM.other_config["automojo-run-id"]``
        marker; the neutral tag list is recovered from ``other_config`` by
        the :class:`XenTagTranslator`.  Guest IP reporting is read from the
        XenTools-populated ``other_config`` map when present.
    """

    def __init__(self, *, client: Any,
                 output_root: str = ".output") -> None:
        """
            Construct an XenInventory.

            :param client: The :class:`XenClient`.
            :param output_root: The output root directory.
        """
        self._client = client
        self._output_root = output_root
        self._translator = XenTagTranslator()
        return

    def list_run(self, *, run_id: str,
                 aspects: Any) -> List[ProvisionedResource]:
        """
            Enumerate every run-owned VM across the Pool.

            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.

            :returns: A list of :class:`ProvisionedResource` records.
        """
        out: List[ProvisionedResource] = []
        for vm in self._client.Vms.list(aspects=aspects):
            if self._translator.run_id_of(vm_record=vm) != run_id:
                continue
            tags = self._translator.from_xen(vm_record=vm)
            guest_ip = self._guest_ip_of(vm=vm)
            out.append(ProvisionedResource(
                kind="instance", name=vm.name_label, venue_id=vm.uuid,
                attributes={"vm_uuid": vm.uuid,
                            "power_state": vm.power_state,
                            "vcpus": vm.vcpus_max,
                            "memory_bytes": vm.memory_static_max,
                            "ip": guest_ip},
                tags=tags))
        rtnval = out
        return rtnval

    @staticmethod
    def _guest_ip_of(*, vm: Any) -> str:
        """
            Read the XenTools-reported guest IP from a VM record.

            XenTools writes the guest networking facts into ``other_config``
            under keypaths such as ``networks/0/ip``; the inventory reads the
            first such entry when present.

            :param vm: The XenVm record.

            :returns: The guest IP string, or an empty string when absent.
        """
        other_config = getattr(vm, "other_config", None)
        if other_config is None:
            rtnval = ""
            return rtnval

        for key in sorted(other_config.keys()):
            if key.startswith("networks/") and key.endswith("/ip"):
                rtnval = other_config[key]
                return rtnval

        rtnval = other_config.get("guest-ip", "")
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
