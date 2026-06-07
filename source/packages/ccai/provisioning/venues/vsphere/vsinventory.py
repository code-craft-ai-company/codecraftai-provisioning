"""
    .. module:: vsinventory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: VsInventory — enumerates VSphere venue resources owned by a
        provisioning run.

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


class VsInventory:
    """
        Enumerates the VMs and distributed port groups a run created.

        Resources are identified by the run-id naming prefix
        ``<run-id>-<name>`` applied to created vCenter objects, mirroring the
        ``codecraftai-run-id`` tag the venue attaches.
    """

    def __init__(self, *, ops: Any) -> None:
        """
            Construct a VsInventory.

            :param ops: A VSphereOps facade.
        """
        self._ops: Any = ops
        return

    def list_run(self, *, spec: Any, run_id: str, aspects: Any
                 ) -> List[ProvisionedResource]:
        """
            Enumerate run-owned VMs and port groups.

            :param spec: The VSphereSpec (used to map prefixed names back to
                         neutral names).
            :param run_id: Run identifier.
            :param aspects: Behaviour controls.

            :returns: A list of ProvisionedResource entries with observed
                      IP addresses.
        """
        out: List[ProvisionedResource] = []

        if spec is None:
            rtnval = out
            return rtnval

        vm_name_to_neutral: Dict[str, str] = {}
        for instance in spec.instances:
            vm_name_to_neutral["{}-{}".format(run_id, instance.name)] = instance.name

        pg_name_to_neutral: Dict[str, str] = {}
        for subnet in spec.subnets:
            pg_name_to_neutral["{}-{}".format(run_id, subnet.name)] = subnet.name

        for vm in self._ops.list_vms(aspects=aspects):
            vm_name = getattr(vm, "name", None)
            if vm_name is None or vm_name not in vm_name_to_neutral:
                continue
            ip_addresses = getattr(vm, "ip_addresses", None)
            attributes: Dict[str, Any] = {
                "vm_name": vm_name,
                "power_state": getattr(vm, "power_state", None),
                "ip_addresses": list(ip_addresses) if ip_addresses is not None else [],
            }
            out.append(ProvisionedResource(
                kind="instance", name=vm_name_to_neutral[vm_name],
                venue_id=getattr(vm, "vm", vm_name),
                attributes=attributes,
            ))

        for net in self._ops.list_networks(aspects=aspects):
            net_name = getattr(net, "name", None)
            if net_name is None or net_name not in pg_name_to_neutral:
                continue
            out.append(ProvisionedResource(
                kind="subnet", name=pg_name_to_neutral[net_name],
                venue_id=getattr(net, "network", net_name),
                attributes={"port_group": net_name},
            ))

        rtnval = out
        return rtnval

    @staticmethod
    def persist(*, resources: List[ProvisionedResource], run_id: str,
                output_root: str = ".output/provisioning") -> str:
        """
            Persist the inventory to a run-scoped JSON file.

            :param resources: The resources to persist.
            :param run_id: Run identifier (the per-run directory name).
            :param output_root: Root directory for provisioning output.

            :returns: The path of the written inventory file.
        """
        run_dir = os.path.join(output_root, run_id)
        os.makedirs(run_dir, exist_ok=True)
        out_path = os.path.join(run_dir, "vsphere-inventory.json")

        records: List[Dict[str, Any]] = []
        for resource in resources:
            records.append({
                "kind": resource.kind,
                "name": resource.name,
                "venue_id": resource.venue_id,
                "attributes": resource.attributes,
            })

        with open(out_path, "w", encoding="utf-8") as out_file:
            json.dump(records, out_file, indent=2, sort_keys=True)

        rtnval = out_path
        return rtnval
