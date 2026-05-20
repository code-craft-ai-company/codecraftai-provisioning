"""
    .. module:: provisioningplan
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: ProvisioningPlan record for a single venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.restclient.base.schemaobject import SchemaObject
from automojo.restclient.base.schemafield import Field

from automojo.provisioning.model.cloud.plannedaction import PlannedAction


class ProvisioningPlan(SchemaObject):
    """
        Per-venue provisioning plan.

        Wraps a list of PlannedAction entries describing the per-resource
        intents (CREATE/UPDATE/SKIP/DELETE) the venue provisioner would
        execute on apply.
    """

    actions = Field(list, required=False, default=None)

    def __init__(self, *, actions: Optional[List[PlannedAction]] = None) -> None:
        """
            Construct a ProvisioningPlan.

            :param actions: List of PlannedAction entries (order matters).
        """
        effective_actions = actions if actions is not None else []
        super().__init__(actions=effective_actions)
        return

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProvisioningPlan":
        """
            Reconstruct a ProvisioningPlan from a serialised payload.

            :param data: Serialised payload.

            :returns: A ProvisioningPlan instance.
        """
        if not isinstance(data, dict):
            return data  # type: ignore

        raw_actions = data.get("actions", None)
        promoted: List[PlannedAction] = []
        if raw_actions is not None:
            for entry in raw_actions:
                if isinstance(entry, PlannedAction):
                    promoted.append(entry)
                else:
                    promoted.append(PlannedAction.from_dict(entry))

        rtnval = cls(actions=promoted)
        return rtnval
