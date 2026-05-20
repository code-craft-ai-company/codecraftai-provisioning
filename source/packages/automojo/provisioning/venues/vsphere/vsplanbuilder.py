"""
    .. module:: vsplanbuilder
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: VsPlanBuilder — computes a CREATE/SKIP/UPDATE plan for the
        VSphere venue by reading current vCenter inventory.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict

from automojo.provisioning.model.cloud.plannedaction import PlannedAction
from automojo.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)
from automojo.provisioning.model.cloud.provisioningplan import ProvisioningPlan
from automojo.provisioning.venues.vsphere.vspherevenueconfig import (
    VSphereVenueConfig
)


class VsPlanBuilder:
    """
        Builds a :class:`ProvisioningPlan` for a VSphereSpec.

        Performs read-only inventory queries; emits CREATE for absent
        resources, SKIP for present-and-matching resources, and UPDATE for
        present-but-drifted resources.
    """

    def __init__(self, *, ops: Any, config: VSphereVenueConfig) -> None:
        """
            Construct a VsPlanBuilder.

            :param ops: A VSphereOps facade.
            :param config: The VSphereVenueConfig.
        """
        self._ops: Any = ops
        self._config: VSphereVenueConfig = config
        return

    def plan(self, *, spec: Any, run_id: str, aspects: Any
             ) -> ProvisioningPlan:
        """
            Compute the plan for a VSphereSpec.

            :param spec: The VSphereSpec.
            :param run_id: Run identifier.
            :param aspects: Behaviour controls.

            :returns: A ProvisioningPlan.
        """
        actions = []

        if spec is None:
            rtnval = ProvisioningPlan(actions=actions)
            return rtnval

        existing_networks = self._ops.list_networks(aspects=aspects)
        network_names = set()
        for net in existing_networks:
            net_name = getattr(net, "name", None)
            if net_name is not None:
                network_names.add(net_name)

        vlan_map = self._config.subnet_vlan_ids
        for subnet in spec.subnets:
            pg_name = "{}-{}".format(run_id, subnet.name)
            if pg_name not in network_names:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="subnet", resource_name=subnet.name,
                ))
            else:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="subnet", resource_name=subnet.name,
                    diff={"vlan_id": vlan_map.get(subnet.name, 0)},
                ))

        existing_vms = self._ops.list_vms(aspects=aspects)
        vm_names = set()
        for vm in existing_vms:
            vm_name = getattr(vm, "name", None)
            if vm_name is not None:
                vm_names.add(vm_name)

        for instance in spec.instances:
            vm_name = "{}-{}".format(run_id, instance.name)
            if vm_name not in vm_names:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="instance", resource_name=instance.name,
                ))
            else:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="instance", resource_name=instance.name,
                ))

        for volume in spec.volumes:
            actions.append(PlannedAction(
                intent=PlannedActionIntent.CREATE,
                resource_kind="volume", resource_name=volume.name,
            ))

        rtnval = ProvisioningPlan(actions=actions)
        return rtnval
