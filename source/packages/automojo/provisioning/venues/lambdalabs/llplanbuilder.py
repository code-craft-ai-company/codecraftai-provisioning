"""
    .. module:: llplanbuilder
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: LlPlanBuilder — computes the CREATE/SKIP/UPDATE plan for the
               Lambda Labs venue provisioner.

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
from automojo.provisioning.venues.lambdalabs.llnaming import instance_name_for
from automojo.provisioning.venues.lambdalabs.llresolver import LlResolver
from automojo.provisioning.venues.lambdalabs.lambdalabsspec import (
    LambdalabsSpec
)


class LlPlanBuilder:
    """
        Builds a :class:`ProvisioningPlan` for a :class:`LambdalabsSpec`.

        Plan reads venue state through the interop client and emits one
        :class:`PlannedAction` per resource: CREATE when absent, SKIP when
        already-launched in shape, and UPDATE-by-recreate when the live
        instance type drifts from the spec (Lambda Labs offers no live
        instance-type update).
    """

    def __init__(self, *, client: Any, resolver: LlResolver) -> None:
        """
            Construct an LlPlanBuilder.

            :param client: The Lambda Labs interop client.
            :param resolver: The :class:`LlResolver`.
        """
        self._client = client
        self._resolver = resolver
        return

    def plan(self, *, spec: LambdalabsSpec, run_id: str,
             aspects: Any) -> ProvisioningPlan:
        """
            Compute the CREATE/SKIP/UPDATE plan.

            :param spec: The :class:`LambdalabsSpec`.
            :param run_id: The provisioning run id.
            :param aspects: Behaviour control passed to the interop client.

            :returns: A :class:`ProvisioningPlan`.
        """
        actions: List[PlannedAction] = []

        if spec is None:
            rtnval = ProvisioningPlan(actions=actions)
            return rtnval

        live_keys = self._client.list_ssh_keys(aspects=aspects)
        live_key_names: List[str] = []
        for key in live_keys:
            live_key_names.append(key.name)

        for keypair in spec.keypairs:
            if keypair.name in live_key_names:
                intent = PlannedActionIntent.SKIP
            else:
                intent = PlannedActionIntent.CREATE
            actions.append(PlannedAction(intent=intent,
                                         resource_kind="keypair",
                                         resource_name=keypair.name))

        live_instances = self._client.list_instances(aspects=aspects)
        live_by_name: Dict[str, Any] = {}
        for instance in live_instances:
            live_by_name[instance.name] = instance

        for inst in spec.instances:
            venue_name = instance_name_for(spec_name=inst.name,
                                           run_id=run_id)
            existing = live_by_name.get(venue_name, None)
            resolution = self._resolver.resolve_instance_type(instance=inst)

            if resolution is not None and resolution.is_cluster:
                resource_kind = "cluster"
            else:
                resource_kind = "instance"

            if existing is None:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind=resource_kind,
                    resource_name=inst.name,
                ))
                continue

            desired_slug: Optional[str] = None
            if resolution is not None:
                desired_slug = resolution.instance_type_slug

            if desired_slug is not None and existing.instance_type_name != desired_slug:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.UPDATE,
                    resource_kind=resource_kind,
                    resource_name=inst.name,
                    diff={"before": {"instance_type": existing.instance_type_name},
                          "after": {"instance_type": desired_slug},
                          "note": "Lambda Labs has no live instance-type "
                                  "update; UPDATE is realised by recreate."},
                ))
            else:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind=resource_kind,
                    resource_name=inst.name,
                ))

        rtnval = ProvisioningPlan(actions=actions)
        return rtnval
