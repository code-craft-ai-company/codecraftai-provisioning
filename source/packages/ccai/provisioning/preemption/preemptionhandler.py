"""
    .. module:: preemptionhandler
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: handle_preemption — dispatches a preemption notice onto its
               PreemptionPolicy branch.

    The §7.6 plan decision makes `FAIL` the default policy precisely because a
    silent reacquisition during `apply` would hide capacity problems behind
    quietly-degraded reruns.  This module encodes the three policy branches the
    venue provisioners consult at their match-then-act (`apply`) and poll
    (`verify`) points:

        FAIL        — raise ProvisioningPreemptionError; the failure stays loud.
        REACQUIRE   — recreate the instance with the same spec under a new
                      venue id; log a WARNING with the old and new ids.
        BEST_EFFORT — drop the instance from inventory and continue; log INFO.

    See also: cloud-provisioner-lifecycle (match-then-act helpers that consult
    the policy) and provisioning-engine-pipeline (apply / verify stages that
    call this handler).

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import logging
import os

from typing import Any, Optional, Union

from ccai.provisioning.model.cloud.preemptionpolicy import PreemptionPolicy
from ccai.provisioning.model.cloud.cloudinstance import CloudInstance
from ccai.provisioning.model.cloud.cloudprovisioner import CloudProvisioner
from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.preemption.preemptionerrors import (
    ProvisioningPreemptionError
)
from ccai.provisioning.preemption.preemptionevent import PreemptionEvent


logger = logging.getLogger(__name__)


# Stages from which the handler may be invoked.  `destroy` is intentionally
# excluded: a preemption noticed during teardown is logged and the resource is
# treated as already-gone (idempotent destroy) regardless of policy.
_HANDLER_STAGES = ("apply", "verify")


def _coerce_policy(policy: Union[PreemptionPolicy, str]) -> PreemptionPolicy:
    """
        Coerce a policy argument into a PreemptionPolicy enum member.

        :param policy: A PreemptionPolicy or its string value.

        :returns: The PreemptionPolicy enum member.
        :raises: ProvisioningPreemptionError
    """
    if isinstance(policy, PreemptionPolicy):
        rtnval = policy
        return rtnval

    if isinstance(policy, str):
        try:
            rtnval = PreemptionPolicy(policy)
        except ValueError:
            err_msg_lines = ["Unknown preemption policy."]
            err_msg_lines.append("    GOT: {!r}".format(policy))
            valid = ", ".join(p.value for p in PreemptionPolicy)
            err_msg_lines.append("    EXPECTED ONE OF: {}".format(valid))
            err_msg = os.linesep.join(err_msg_lines)
            raise ProvisioningPreemptionError(err_msg) from None
        return rtnval

    raise ProvisioningPreemptionError(
        "policy must be a PreemptionPolicy or str."
    )


def _handle_fail(*, event: PreemptionEvent) -> None:
    """
        FAIL branch — raise a loud, contextual ProvisioningPreemptionError.

        :param event: The PreemptionEvent describing the preemption notice.

        :raises: ProvisioningPreemptionError
    """
    err_msg_lines = ["Instance preempted while preemption_policy=FAIL."]
    err_msg_lines.append("    INSTANCE: {}".format(event.instance_name))
    err_msg_lines.append("    VENUE_ID: {}".format(event.venue_id))
    err_msg_lines.append("    STAGE:    {}".format(event.detected_at_stage))
    if event.reason is not None:
        err_msg_lines.append("    REASON:   {}".format(event.reason))
    err_msg_lines.append("    POLICY:   {}".format(event.policy))
    err_msg = os.linesep.join(err_msg_lines)
    raise ProvisioningPreemptionError(err_msg)


def _refresh_reacquire_inputs(*, spec: CloudInstance,
                              provisioner: CloudProvisioner,
                              event: PreemptionEvent,
                              aspects: Any) -> None:
    """
        Refresh the inputs a REACQUIRE replacement needs before recreation.

        A reclaimed instance is replaced under a new venue id, so two inputs
        captured at the original create time are usually stale by the time the
        replacement is launched:

            1. The ephemeral VPN auth key — short-lived control-plane keys have
               almost always expired by the time a preemption is noticed.
            2. The rendered cloud-init document — it embeds the auth key and
               the instance identity, so it must be re-rendered for the
               replacement.

        Both refreshes are delegated to optional provisioner hooks so each
        venue keeps ownership of its own auth-key minting and cloud-init
        rendering.  A venue that implements neither hook (for example a venue
        whose instances never carry ``vpn_join``) is simply left untouched.

        :param spec: The CloudInstance spec being recreated.
        :param provisioner: The venue provisioner performing the recreation.
        :param event: The PreemptionEvent describing the preemption notice.
        :param aspects: Aspects controlling the recreation behaviour.
    """
    if spec.vpn_join is not None:
        refresh_authkey_hook = getattr(provisioner, "refresh_vpn_authkey",
                                       None)
        if refresh_authkey_hook is not None and callable(refresh_authkey_hook):
            refresh_authkey_hook(spec=spec, aspects=aspects)
            logger.info(
                "Preemption REACQUIRE: refreshed ephemeral VPN auth key for "
                "instance=%s prior to recreation.",
                event.instance_name,
            )

    render_hook = getattr(provisioner, "render_cloud_init", None)
    if render_hook is not None and callable(render_hook):
        render_hook(spec=spec, aspects=aspects)
        logger.info(
            "Preemption REACQUIRE: re-rendered cloud-init for instance=%s "
            "prior to recreation.",
            event.instance_name,
        )
    return


def _handle_reacquire(*, spec: CloudInstance, provisioner: CloudProvisioner,
                      event: PreemptionEvent,
                      aspects: Any) -> ProvisionedResource:
    """
        REACQUIRE branch — recreate the instance under a new venue id.

        Delegates the actual recreation to the provisioner's
        ``reacquire_instance`` hook so each venue can reuse its own cloud-init
        renderer and (re)mint an ephemeral auth key when the original has
        expired.

        :param spec: The CloudInstance spec to recreate.
        :param provisioner: The venue provisioner performing the recreation.
        :param event: The PreemptionEvent describing the preemption notice.
        :param aspects: Aspects controlling the recreation behaviour.

        :returns: The ProvisionedResource for the replacement instance.
        :raises: ProvisioningPreemptionError
    """
    _refresh_reacquire_inputs(spec=spec, provisioner=provisioner,
                              event=event, aspects=aspects)

    reacquire_hook = getattr(provisioner, "reacquire_instance", None)
    if reacquire_hook is None or not callable(reacquire_hook):
        err_msg_lines = [
            "Venue provisioner does not implement reacquire_instance; "
            "cannot honour preemption_policy=REACQUIRE."
        ]
        err_msg_lines.append("    INSTANCE: {}".format(event.instance_name))
        err_msg_lines.append(
            "    PROVISIONER: {}".format(type(provisioner).__name__)
        )
        err_msg = os.linesep.join(err_msg_lines)
        raise ProvisioningPreemptionError(err_msg)

    replacement = reacquire_hook(spec=spec, aspects=aspects)

    if not isinstance(replacement, ProvisionedResource):
        err_msg_lines = [
            "reacquire_instance returned a non-ProvisionedResource value."
        ]
        err_msg_lines.append("    INSTANCE: {}".format(event.instance_name))
        err_msg_lines.append("    GOT: {!r}".format(type(replacement)))
        err_msg = os.linesep.join(err_msg_lines)
        raise ProvisioningPreemptionError(err_msg)

    event.original_venue_id = event.venue_id
    event.replacement_venue_id = replacement.venue_id

    logger.warning(
        "Preemption REACQUIRE: instance=%s stage=%s original_venue_id=%s "
        "replacement_venue_id=%s",
        event.instance_name, event.detected_at_stage,
        event.original_venue_id, event.replacement_venue_id,
    )

    rtnval = replacement
    return rtnval


def _handle_best_effort(*, event: PreemptionEvent) -> None:
    """
        BEST_EFFORT branch — drop the instance from inventory, log INFO.

        :param event: The PreemptionEvent describing the preemption notice.
    """
    logger.info(
        "Preemption BEST_EFFORT: dropping instance=%s venue_id=%s stage=%s "
        "from inventory and continuing.",
        event.instance_name, event.venue_id, event.detected_at_stage,
    )
    return


def handle_preemption(*, spec: CloudInstance,
                      policy: Union[PreemptionPolicy, str],
                      provisioner: CloudProvisioner,
                      stage: str,
                      aspects: Any,
                      venue_id: str,
                      reason: Optional[str] = None
                      ) -> Optional[ProvisionedResource]:
    """
        Apply a preemption notice onto its PreemptionPolicy branch.

        A structured PreemptionEvent is built for every call and logged at the
        branch's severity, so a downstream coordinator always sees the decision.

        :param spec: The CloudInstance whose instance was preempted.
        :param policy: The PreemptionPolicy in effect for the instance.
        :param provisioner: The venue provisioner that observed the preemption.
        :param stage: The lifecycle stage ("apply" or "verify").
        :param aspects: Aspects controlling reacquisition behaviour.
        :param venue_id: The venue-side identifier that was reclaimed.
        :param reason: Optional venue-supplied preemption reason.

        :returns: A ProvisionedResource for the replacement instance when the
                  policy is REACQUIRE; None when the policy is BEST_EFFORT.
        :raises: ProvisioningPreemptionError
    """
    if stage not in _HANDLER_STAGES:
        err_msg_lines = ["handle_preemption invoked with an invalid stage."]
        err_msg_lines.append("    GOT: {!r}".format(stage))
        err_msg_lines.append(
            "    EXPECTED ONE OF: {}".format(", ".join(_HANDLER_STAGES))
        )
        err_msg = os.linesep.join(err_msg_lines)
        raise ProvisioningPreemptionError(err_msg)

    if not isinstance(spec, CloudInstance):
        raise ProvisioningPreemptionError(
            "spec must be a CloudInstance instance."
        )

    resolved_policy = _coerce_policy(policy=policy)

    event = PreemptionEvent(instance_name=spec.name, venue_id=venue_id,
                            detected_at_stage=stage,
                            policy=resolved_policy, reason=reason)

    if resolved_policy == PreemptionPolicy.FAIL:
        _handle_fail(event=event)
        # _handle_fail always raises; this line is never reached.
        rtnval: Optional[ProvisionedResource] = None
        return rtnval

    if resolved_policy == PreemptionPolicy.REACQUIRE:
        replacement = _handle_reacquire(spec=spec, provisioner=provisioner,
                                        event=event, aspects=aspects)
        rtnval = replacement
        return rtnval

    if resolved_policy == PreemptionPolicy.BEST_EFFORT:
        _handle_best_effort(event=event)
        rtnval = None
        return rtnval

    err_msg_lines = ["handle_preemption reached an unhandled policy branch."]
    err_msg_lines.append("    POLICY: {!r}".format(resolved_policy))
    err_msg = os.linesep.join(err_msg_lines)
    raise ProvisioningPreemptionError(err_msg)
