"""
    .. module:: ntxplanbuilder
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: NtxPlanBuilder — computes the CREATE/SKIP/UPDATE plan for the
               Nutanix venue provisioner.

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

from automojo.provisioning.venues.nutanix.nutanixspec import NutanixSpec
from automojo.provisioning.venues.nutanix.nutanixvenueconfig import (
    NutanixVenueConfig
)
from automojo.provisioning.venues.nutanix.ntxnaming import resource_name_for
from automojo.provisioning.venues.nutanix.ntxresolver import NtxResolver


class NtxPlanBuilder:
    """
        Builds a :class:`ProvisioningPlan` for a :class:`NutanixSpec`.

        Plan reads Prism Central state through the interop client and
        emits one :class:`PlannedAction` per Network (Flow VPC), Subnet,
        Security Policy, Volume and VM: CREATE when the venue-side name is
        absent, SKIP when already present, and UPDATE when a VM's
        vCPU / memory drifts from the spec's resolved hardware.  Plan
        performs no mutation.
    """

    def __init__(self, *, client: Any, config: NutanixVenueConfig,
                 resolver: Optional[NtxResolver] = None) -> None:
        """
            Construct an NtxPlanBuilder.

            :param client: The Nutanix interop client.
            :param config: The :class:`NutanixVenueConfig`.
            :param resolver: Optional :class:`NtxResolver`; defaults to a
                fresh instance bound to ``client`` and ``config``.
        """
        self._client = client
        self._config = config
        if resolver is not None:
            self._resolver: NtxResolver = resolver
        else:
            self._resolver = NtxResolver(client=client, config=config)
        return

    def plan(self, *, spec: Optional[NutanixSpec], run_id: str,
             aspects: Any) -> ProvisioningPlan:
        """
            Compute the CREATE/SKIP/UPDATE plan.

            :param spec: The :class:`NutanixSpec`, or ``None``.
            :param run_id: The provisioning run id.
            :param aspects: Behaviour control passed to the interop
                client.

            :returns: A :class:`ProvisioningPlan`.
        """
        actions: List[PlannedAction] = []

        if spec is None:
            rtnval = ProvisioningPlan(actions=actions)
            return rtnval

        self._plan_networks(spec=spec, run_id=run_id, aspects=aspects,
                            actions=actions)
        self._plan_subnets(spec=spec, run_id=run_id, aspects=aspects,
                           actions=actions)
        self._plan_security_groups(spec=spec, run_id=run_id,
                                   aspects=aspects, actions=actions)
        self._plan_volumes(spec=spec, run_id=run_id, aspects=aspects,
                           actions=actions)
        self._plan_instances(spec=spec, run_id=run_id, aspects=aspects,
                             actions=actions)

        rtnval = ProvisioningPlan(actions=actions)
        return rtnval

    def _plan_networks(self, *, spec: NutanixSpec, run_id: str,
                       aspects: Any,
                       actions: List[PlannedAction]) -> None:
        """
            Append the Flow VPC actions to the plan.

            :param spec: The :class:`NutanixSpec`.
            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.
            :param actions: The accumulating action list.

            :returns: ``None``.
        """
        live = self._client.vpcs.list(aspects=aspects)
        live_names: List[str] = []
        for vpc in live:
            live_names.append(vpc.name)

        for network in spec.networks:
            venue_name = resource_name_for(spec_name=network.name,
                                           run_id=run_id)
            if venue_name in live_names:
                intent = PlannedActionIntent.SKIP
            else:
                intent = PlannedActionIntent.CREATE
            actions.append(PlannedAction(intent=intent,
                                         resource_kind="network",
                                         resource_name=network.name))
        return

    def _plan_subnets(self, *, spec: NutanixSpec, run_id: str,
                      aspects: Any,
                      actions: List[PlannedAction]) -> None:
        """
            Append the subnet actions to the plan.

            :param spec: The :class:`NutanixSpec`.
            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.
            :param actions: The accumulating action list.

            :returns: ``None``.
        """
        live = self._client.subnets.list(aspects=aspects)
        live_names: List[str] = []
        for subnet in live:
            live_names.append(subnet.name)

        for subnet in spec.subnets:
            venue_name = resource_name_for(spec_name=subnet.name,
                                           run_id=run_id)
            if venue_name in live_names:
                intent = PlannedActionIntent.SKIP
            else:
                intent = PlannedActionIntent.CREATE
            actions.append(PlannedAction(intent=intent,
                                         resource_kind="subnet",
                                         resource_name=subnet.name))
        return

    def _plan_security_groups(self, *, spec: NutanixSpec, run_id: str,
                              aspects: Any,
                              actions: List[PlannedAction]) -> None:
        """
            Append the Flow security-policy actions to the plan.

            :param spec: The :class:`NutanixSpec`.
            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.
            :param actions: The accumulating action list.

            :returns: ``None``.
        """
        live = self._client.security_policies.list(aspects=aspects)
        live_names: List[str] = []
        for policy in live:
            live_names.append(policy.name)

        for sg in spec.security_groups:
            venue_name = resource_name_for(spec_name=sg.name,
                                           run_id=run_id)
            if venue_name in live_names:
                intent = PlannedActionIntent.SKIP
            else:
                intent = PlannedActionIntent.CREATE
            actions.append(PlannedAction(intent=intent,
                                         resource_kind="security_group",
                                         resource_name=sg.name))
        return

    def _plan_volumes(self, *, spec: NutanixSpec, run_id: str,
                      aspects: Any,
                      actions: List[PlannedAction]) -> None:
        """
            Append the volume-group actions to the plan.

            :param spec: The :class:`NutanixSpec`.
            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.
            :param actions: The accumulating action list.

            :returns: ``None``.
        """
        live = self._client.volume_groups.list(aspects=aspects)
        live_names: List[str] = []
        for volume_group in live:
            live_names.append(volume_group.name)

        for volume in spec.volumes:
            venue_name = resource_name_for(spec_name=volume.name,
                                           run_id=run_id)
            if venue_name in live_names:
                intent = PlannedActionIntent.SKIP
            else:
                intent = PlannedActionIntent.CREATE
            actions.append(PlannedAction(intent=intent,
                                         resource_kind="volume",
                                         resource_name=volume.name))
        return

    def _plan_instances(self, *, spec: NutanixSpec, run_id: str,
                        aspects: Any,
                        actions: List[PlannedAction]) -> None:
        """
            Append the VM actions to the plan.

            :param spec: The :class:`NutanixSpec`.
            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.
            :param actions: The accumulating action list.

            :returns: ``None``.
        """
        live = self._client.vms.list(aspects=aspects)
        live_by_name: Dict[str, Any] = {}
        for vm in live:
            live_by_name[vm.name] = vm

        for instance in spec.instances:
            venue_name = resource_name_for(spec_name=instance.name,
                                           run_id=run_id)
            existing = live_by_name.get(venue_name, None)

            if existing is None:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="instance",
                    resource_name=instance.name,
                ))
                continue

            hardware = self._resolver.size_to_hardware(
                size_hint=instance.size
            )
            desired_vcpus = hardware["num_vcpus"]
            desired_memory_mib = hardware["memory_mib"]

            drift = (existing.num_vcpus != desired_vcpus
                     or existing.memory_mib != desired_memory_mib)
            if drift:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.UPDATE,
                    resource_kind="instance",
                    resource_name=instance.name,
                    diff={"before": {"num_vcpus": existing.num_vcpus,
                                     "memory_mib": existing.memory_mib},
                          "after": {"num_vcpus": desired_vcpus,
                                    "memory_mib": desired_memory_mib},
                          "note": "Nutanix vCPU/memory drift; UPDATE is "
                                  "realised by an in-place PUT honouring "
                                  "AHV hot-plug rules where possible."},
                ))
            else:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="instance",
                    resource_name=instance.name,
                ))
        return
