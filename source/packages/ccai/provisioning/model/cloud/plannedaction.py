"""
    .. module:: plannedaction
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: PlannedAction record describing one intent against a resource.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, Optional, Union

from ccai.restclient.base.schemaobject import SchemaObject
from ccai.restclient.base.schemafield import Field

from ccai.provisioning.model.exceptions import SchemaValidationError
from ccai.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)


class PlannedAction(SchemaObject):
    """
        One intended action against a single resource within a plan.

        A plan is a list of PlannedAction records, each pinning the intent
        (CREATE/UPDATE/SKIP/DELETE), the resource kind and name, and a diff
        describing the shape of the change for UPDATE intents.
    """

    intent = Field(str, required=True)
    resource_kind = Field(str, required=True)
    resource_name = Field(str, required=True)
    diff = Field(dict, required=False, default=None)

    def __init__(self, *, intent: Union[PlannedActionIntent, str],
                 resource_kind: str, resource_name: str,
                 diff: Optional[Dict[str, Any]] = None) -> None:
        """
            Construct a PlannedAction.

            :param intent: PlannedActionIntent value.
            :param resource_kind: The resource kind string.
            :param resource_name: The resource name.
            :param diff: Optional diff payload.

            :raises: SchemaValidationError
        """
        if isinstance(intent, PlannedActionIntent):
            intent_value = intent.value
        elif isinstance(intent, str):
            try:
                intent_value = PlannedActionIntent(intent).value
            except ValueError:
                raise SchemaValidationError(
                    "intent must be a PlannedActionIntent value, got {!r}".format(
                        intent
                    )
                ) from None
        else:
            raise SchemaValidationError(
                "intent must be PlannedActionIntent or str."
            )

        if resource_kind is None or len(resource_kind) == 0:
            raise SchemaValidationError("resource_kind must not be empty.")

        if resource_name is None or len(resource_name) == 0:
            raise SchemaValidationError("resource_name must not be empty.")

        effective_diff = diff if diff is not None else {}

        super().__init__(intent=intent_value, resource_kind=resource_kind,
                         resource_name=resource_name, diff=effective_diff)
        return

    @property
    def intent_enum(self) -> PlannedActionIntent:
        """
            Return the intent as the enum value.

            :returns: The PlannedActionIntent.
        """
        rtnval = PlannedActionIntent(self.intent)
        return rtnval
