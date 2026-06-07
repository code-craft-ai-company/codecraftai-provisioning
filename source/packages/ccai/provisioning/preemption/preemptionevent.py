"""
    .. module:: preemptionevent
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: PreemptionEvent — the typed record of a single preemption notice.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Any, Dict, Optional, Union

from ccai.restclient.base.schemaobject import SchemaObject
from ccai.restclient.base.schemafield import Field

from ccai.provisioning.model.exceptions import SchemaValidationError
from ccai.provisioning.model.cloud.preemptionpolicy import PreemptionPolicy


# The lifecycle stages at which a preemption can be detected.  Detection at
# `destroy` is recorded but never triggers reacquisition (see design §Destroy
# Interaction).
_VALID_STAGES = ("apply", "verify", "destroy")


class PreemptionEvent(SchemaObject):
    """
        Typed record of a single preemption notice.

        Carries the logical instance name, the venue-side id that was
        reclaimed, the lifecycle stage at which the preemption was detected,
        the policy in effect, and — when the policy is `REACQUIRE` — the
        original and replacement venue ids.  Used both for structured logging
        and as the round-trippable payload persisted with a run.
    """

    instance_name = Field(str, required=True)
    venue_id = Field(str, required=True)
    detected_at_stage = Field(str, required=True)
    policy = Field(str, required=True)
    original_venue_id = Field(str, required=False, default=None)
    replacement_venue_id = Field(str, required=False, default=None)
    reason = Field(str, required=False, default=None)

    def __init__(self, *, instance_name: str, venue_id: str,
                 detected_at_stage: str,
                 policy: Union[PreemptionPolicy, str],
                 original_venue_id: Optional[str] = None,
                 replacement_venue_id: Optional[str] = None,
                 reason: Optional[str] = None) -> None:
        """
            Construct a PreemptionEvent.

            :param instance_name: Logical name of the preempted instance.
            :param venue_id: Venue-side identifier that was reclaimed.
            :param detected_at_stage: One of "apply", "verify", "destroy".
            :param policy: The PreemptionPolicy in effect.
            :param original_venue_id: Venue id before a REACQUIRE replacement.
            :param replacement_venue_id: Venue id of a REACQUIRE replacement.
            :param reason: Optional venue-supplied preemption reason.

            :raises: SchemaValidationError
        """
        if instance_name is None or len(instance_name) == 0:
            raise SchemaValidationError("instance_name must not be empty.")

        if venue_id is None or len(venue_id) == 0:
            raise SchemaValidationError("venue_id must not be empty.")

        if detected_at_stage not in _VALID_STAGES:
            err_msg_lines = ["detected_at_stage has an invalid value."]
            err_msg_lines.append("    GOT: {!r}".format(detected_at_stage))
            err_msg_lines.append(
                "    EXPECTED ONE OF: {}".format(", ".join(_VALID_STAGES))
            )
            err_msg = os.linesep.join(err_msg_lines)
            raise SchemaValidationError(err_msg)

        if isinstance(policy, PreemptionPolicy):
            policy_value = policy.value
        elif isinstance(policy, str):
            try:
                policy_value = PreemptionPolicy(policy).value
            except ValueError:
                err_msg_lines = ["policy has an invalid value."]
                err_msg_lines.append("    GOT: {!r}".format(policy))
                valid = ", ".join(p.value for p in PreemptionPolicy)
                err_msg_lines.append(
                    "    EXPECTED ONE OF: {}".format(valid)
                )
                err_msg = os.linesep.join(err_msg_lines)
                raise SchemaValidationError(err_msg) from None
        else:
            raise SchemaValidationError(
                "policy must be a PreemptionPolicy or str."
            )

        super().__init__(instance_name=instance_name, venue_id=venue_id,
                         detected_at_stage=detected_at_stage,
                         policy=policy_value,
                         original_venue_id=original_venue_id,
                         replacement_venue_id=replacement_venue_id,
                         reason=reason)
        return

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PreemptionEvent":
        """
            Reconstruct a PreemptionEvent from a serialised payload.

            :param data: Serialised payload.

            :returns: A PreemptionEvent instance.
        """
        if not isinstance(data, dict):
            return data  # type: ignore

        rtnval = cls(
            instance_name=data["instance_name"],
            venue_id=data["venue_id"],
            detected_at_stage=data["detected_at_stage"],
            policy=data["policy"],
            original_venue_id=data.get("original_venue_id", None),
            replacement_venue_id=data.get("replacement_venue_id", None),
            reason=data.get("reason", None),
        )
        return rtnval
