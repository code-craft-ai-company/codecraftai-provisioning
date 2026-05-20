"""
    .. module:: pipelineplan
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Multi-venue aggregate PipelinePlan.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional, Tuple

from automojo.restclient.base.schemaobject import SchemaObject
from automojo.restclient.base.schemafield import Field

from automojo.provisioning.model.cloud.provisioningplan import ProvisioningPlan


class PipelinePlan(SchemaObject):
    """
        Aggregate multi-venue provisioning plan.

        Carries per-venue ProvisioningPlan entries plus the topological
        ordering used by the engine to drive intra-stage execution.
    """

    per_venue_plans = Field(dict, required=False, default=None)
    topological_order = Field(list, required=False, default=None)

    def __init__(self, *,
                 per_venue_plans: Optional[Dict[str, ProvisioningPlan]] = None,
                 topological_order: Optional[List[Tuple[str, str]]] = None
                 ) -> None:
        """
            Construct a PipelinePlan.

            :param per_venue_plans: Map of venue name -> ProvisioningPlan.
            :param topological_order: Ordered list of (kind, name) tuples.
        """
        effective_plans = per_venue_plans if per_venue_plans is not None else {}
        effective_order = topological_order if topological_order is not None else []
        super().__init__(per_venue_plans=effective_plans,
                         topological_order=effective_order)
        return

    def total_action_count(self) -> int:
        """
            Return the total number of PlannedAction entries across all venues.

            :returns: Sum of per-venue action lengths.
        """
        rtnval = 0
        for plan in self.per_venue_plans.values():
            rtnval = rtnval + len(plan.actions)
        return rtnval


MultiVenueProvisioningPlan = PipelinePlan
