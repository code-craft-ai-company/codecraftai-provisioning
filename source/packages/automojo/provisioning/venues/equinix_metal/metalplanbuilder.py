"""
    .. module:: metalplanbuilder
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: MetalPlanBuilder — computes the CREATE/SKIP/UPDATE plan for the
               Equinix Metal venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, List

from automojo.provisioning.model.cloud.plannedaction import PlannedAction
from automojo.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)
from automojo.provisioning.model.cloud.provisioningplan import ProvisioningPlan
from automojo.provisioning.venues.equinix_metal.metalapplystages import (
    MetalApplyStages
)
from automojo.provisioning.venues.equinix_metal.metalspec import MetalSpec
from automojo.provisioning.venues.equinix_metal.metaltagtranslator import (
    MetalTagTranslator
)


def _planned_action(*, intent: PlannedActionIntent, resource_kind: str,
                    resource_name: str, diff: Any = None) -> PlannedAction:
    """
        Build a PlannedAction.

        :param intent: PlannedActionIntent.
        :param resource_kind: Kind string.
        :param resource_name: Resource name.
        :param diff: Optional diff payload.

        :returns: A PlannedAction.
    """
    rtnval = PlannedAction(intent=intent, resource_kind=resource_kind,
                           resource_name=resource_name, diff=diff)
    return rtnval


class MetalPlanBuilder:
    """
        Computes a read-only CREATE/SKIP/UPDATE plan for an Equinix Metal
        spec.

        Bare-metal devices cannot be resized in place; when a device's
        hostname or tags drift the plan emits ``UPDATE`` (which the engine
        realises as UPDATE-by-recreate, never an in-place mutation).
    """

    def __init__(self, *, stages: MetalApplyStages) -> None:
        """
            Construct a MetalPlanBuilder.

            :param stages: The MetalApplyStages used for read-side lookups.
        """
        self._stages: MetalApplyStages = stages
        return

    def plan(self, *, spec: MetalSpec, run_id: str,
             aspects: Any) -> ProvisioningPlan:
        """
            Compute the plan.

            :param spec: The MetalSpec.
            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: A ProvisioningPlan.
        """
        actions: List[PlannedAction] = []

        if spec is None:
            rtnval = ProvisioningPlan(actions=actions)
            return rtnval

        for network in spec.networks:
            existing = self._stages.find_vlan(run_id=run_id,
                                              name=network.name)
            if existing is None:
                actions.append(_planned_action(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="network", resource_name=network.name,
                ))
            else:
                actions.append(_planned_action(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="network", resource_name=network.name,
                ))

        for subnet in spec.subnets:
            existing = self._stages.find_ip_reservation(
                run_id=run_id, name=subnet.name
            )
            if existing is None:
                actions.append(_planned_action(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="subnet", resource_name=subnet.name,
                ))
            else:
                actions.append(_planned_action(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="subnet", resource_name=subnet.name,
                ))

        for keypair in spec.keypairs:
            existing = self._stages.find_ssh_key(run_id=run_id,
                                                 name=keypair.name)
            if existing is None:
                actions.append(_planned_action(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="keypair", resource_name=keypair.name,
                ))
            else:
                actions.append(_planned_action(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="keypair", resource_name=keypair.name,
                ))

        for instance in spec.instances:
            existing = self._stages.find_device(run_id=run_id,
                                                name=instance.name)
            if existing is None:
                actions.append(_planned_action(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="instance", resource_name=instance.name,
                ))
            else:
                drift = self._device_drift(existing=existing,
                                           desired=instance)
                if drift is None:
                    actions.append(_planned_action(
                        intent=PlannedActionIntent.SKIP,
                        resource_kind="instance",
                        resource_name=instance.name,
                    ))
                else:
                    actions.append(_planned_action(
                        intent=PlannedActionIntent.UPDATE,
                        resource_kind="instance",
                        resource_name=instance.name,
                        diff=drift,
                    ))

        rtnval = ProvisioningPlan(actions=actions)
        return rtnval

    @staticmethod
    def _device_drift(*, existing: Any, desired: Any) -> Any:
        """
            Compute a hostname / tag drift diff for a device.

            :param existing: Existing device dict.
            :param desired: Desired CloudInstance.

            :returns: A drift diff dict, or None when in shape.
        """
        observed_hostname = existing.get("hostname", "")
        if observed_hostname != desired.name:
            rtnval = {
                "before": {"hostname": observed_hostname},
                "after": {"hostname": desired.name},
                "note": "Metal devices cannot resize; UPDATE-by-recreate.",
            }
            return rtnval

        observed_tags = MetalTagTranslator.flat_dict(
            strings=existing.get("tags", [])
        )
        for entry in desired.tags:
            for key, value in entry.items():
                if observed_tags.get(key, None) != value:
                    rtnval = {
                        "before": {"tags": existing.get("tags", [])},
                        "after": {"tags": desired.tags},
                        "note": ("Metal devices cannot resize; "
                                 "UPDATE-by-recreate."),
                    }
                    return rtnval

        rtnval = None
        return rtnval
