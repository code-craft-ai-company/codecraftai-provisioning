"""
    .. module:: xenplanbuilder
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: XenPlanBuilder — computes the CREATE/SKIP/UPDATE plan for the
        XCP-ng venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.provisioning.model.cloud.plannedaction import PlannedAction
from automojo.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)
from automojo.provisioning.model.cloud.provisioningplan import ProvisioningPlan

from automojo.provisioning.venues.xcpng.xennaming import vm_name_for
from automojo.provisioning.venues.xcpng.xenresolver import XenResolver
from automojo.provisioning.venues.xcpng.xentagtranslator import (
    XenTagTranslator
)
from automojo.provisioning.venues.xcpng.xcpngspec import XcpngSpec


class XenPlanBuilder:
    """
        Builds a :class:`ProvisioningPlan` for an :class:`XcpngSpec`.

        Plan reads venue state through the :class:`XenClient` and emits one
        :class:`PlannedAction` per Network and VM: CREATE when absent, SKIP
        when already present in shape, and UPDATE when a present VM's vCPU
        or memory shape drifts from the spec.
    """

    def __init__(self, *, client: Any, resolver: XenResolver) -> None:
        """
            Construct an XenPlanBuilder.

            :param client: The :class:`XenClient`.
            :param resolver: The :class:`XenResolver`.
        """
        self._client = client
        self._resolver = resolver
        self._translator = XenTagTranslator()
        return

    def plan(self, *, spec: Optional[XcpngSpec], run_id: str,
             aspects: Any) -> ProvisioningPlan:
        """
            Compute the CREATE/SKIP/UPDATE plan.

            :param spec: The :class:`XcpngSpec`, or None.
            :param run_id: The provisioning run id.
            :param aspects: Behaviour control passed to the interop client.

            :returns: A :class:`ProvisioningPlan`.
        """
        actions: List[PlannedAction] = []
        if spec is None:
            rtnval = ProvisioningPlan(actions=actions)
            return rtnval

        self._plan_networks(spec=spec, actions=actions, aspects=aspects)
        self._plan_vms(spec=spec, run_id=run_id, actions=actions,
                       aspects=aspects)

        rtnval = ProvisioningPlan(actions=actions)
        return rtnval

    def _plan_networks(self, *, spec: XcpngSpec,
                       actions: List[PlannedAction], aspects: Any) -> None:
        """
            Append a PlannedAction for each spec Network.

            :param spec: The :class:`XcpngSpec`.
            :param actions: The accumulating action list.
            :param aspects: Behaviour control for the interop client.
        """
        live_networks = self._client.Networks.list(aspects=aspects)
        live_labels: List[str] = []
        for network in live_networks:
            live_labels.append(network.name_label)

        for network in spec.networks:
            if network.name in live_labels:
                intent = PlannedActionIntent.SKIP
            else:
                intent = PlannedActionIntent.CREATE
            actions.append(PlannedAction(intent=intent,
                                         resource_kind="network",
                                         resource_name=network.name))
        return

    def _plan_vms(self, *, spec: XcpngSpec, run_id: str,
                  actions: List[PlannedAction], aspects: Any) -> None:
        """
            Append a PlannedAction for each spec Instance.

            :param spec: The :class:`XcpngSpec`.
            :param run_id: The provisioning run id.
            :param actions: The accumulating action list.
            :param aspects: Behaviour control for the interop client.
        """
        live_vms = self._client.Vms.list(aspects=aspects)
        live_by_name: Dict[str, Any] = {}
        for vm in live_vms:
            live_by_name[vm.name_label] = vm

        for inst in spec.instances:
            venue_name = vm_name_for(spec_name=inst.name, run_id=run_id)
            existing = live_by_name.get(venue_name, None)

            if existing is None:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="instance",
                    resource_name=inst.name))
                continue

            shape = self._resolver.size_to_hardware(size_hint=inst.size)
            drift = self._vm_drift(existing=existing, shape=shape)
            if drift is None:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="instance",
                    resource_name=inst.name))
            else:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.UPDATE,
                    resource_kind="instance",
                    resource_name=inst.name,
                    diff=drift))
        return

    @staticmethod
    def _vm_drift(*, existing: Any,
                  shape: Any) -> Optional[Dict[str, Any]]:
        """
            Compute the vCPU / memory drift between a live VM and a shape.

            :param existing: The live XenVm record.
            :param shape: The resolved :class:`XenHardwareShape`.

            :returns: A diff dict when the VM drifts, else None.
        """
        before: Dict[str, Any] = {}
        after: Dict[str, Any] = {}
        if existing.vcpus_max != shape.vcpus:
            before["vcpus"] = existing.vcpus_max
            after["vcpus"] = shape.vcpus
        if existing.memory_static_max != shape.memory_bytes:
            before["memory_bytes"] = existing.memory_static_max
            after["memory_bytes"] = shape.memory_bytes

        if len(before) == 0:
            rtnval: Optional[Dict[str, Any]] = None
            return rtnval

        rtnval = {
            "before": before,
            "after": after,
            "note": ("XenServer applies vCPU/memory via live set_* calls "
                     "when the VM supports dynamic reconfigure."),
        }
        return rtnval
