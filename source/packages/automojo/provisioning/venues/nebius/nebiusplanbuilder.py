"""
    .. module:: nebiusplanbuilder
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: NebiusPlanBuilder — computes the CREATE/SKIP/UPDATE plan for a
        NebiusSpec.

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
from automojo.provisioning.venues.nebius.nebiusspec import NebiusSpec


def _action(*, intent: PlannedActionIntent, kind: str, name: str,
            diff: Optional[Dict[str, Any]] = None) -> PlannedAction:
    """
        Build a PlannedAction.

        :param intent: The PlannedActionIntent.
        :param kind: Resource kind string.
        :param name: Resource name.
        :param diff: Optional diff payload.

        :returns: A PlannedAction.
    """
    rtnval = PlannedAction(intent=intent, resource_kind=kind,
                           resource_name=name, diff=diff)
    return rtnval


class NebiusPlanBuilder:
    """
        Computes a dry-run :class:`ProvisioningPlan` for a NebiusSpec.

        Reads venue state filtered by the ``automojo-run-id`` label and emits
        a CREATE / SKIP / UPDATE-by-recreate action per resource.  Performs
        no mutation.
    """

    def __init__(self, *, client: Any, resolver: Any) -> None:
        """
            Construct a NebiusPlanBuilder.

            :param client: The NebiusClient (or mock).
            :param resolver: A NebiusResolver used to resolve the desired
                preset for drift detection.
        """
        self._client: Any = client
        self._resolver: Any = resolver
        return

    def _find_owned(self, *, records: List[Any], run_id: str,
                    resource_name: str) -> Optional[Any]:
        """
            Find an owned record by run-id label and resource name label.

            :param records: A list of typed Nebius model records.
            :param run_id: The provisioning run identifier.
            :param resource_name: The neutral resource name.

            :returns: The matching record, or ``None``.
        """
        rtnval: Optional[Any] = None
        for record in records:
            labels = getattr(record, "labels", None)
            if labels is None:
                continue
            if labels.get("automojo-run-id", None) != run_id:
                continue
            if labels.get("automojo-resource-name", None) != resource_name:
                continue
            rtnval = record
            break
        return rtnval

    def plan(self, *, spec: NebiusSpec, run_id: str,
             aspects: Any) -> ProvisioningPlan:
        """
            Compute the provisioning plan for a NebiusSpec.

            :param spec: The NebiusSpec.
            :param run_id: The provisioning run identifier.
            :param aspects: Aspects.

            :returns: A ProvisioningPlan.
        """
        actions: List[PlannedAction] = []

        existing_vpcs = self._client.vpcs.list(project_id=spec.parent_id,
                                               aspects=aspects)
        vpc_by_name: Dict[str, Any] = {}
        for net in spec.networks:
            found = self._find_owned(records=existing_vpcs, run_id=run_id,
                                     resource_name=net.name)
            if found is None:
                actions.append(_action(intent=PlannedActionIntent.CREATE,
                                        kind="network", name=net.name))
            else:
                vpc_by_name[net.name] = found
                actions.append(_action(intent=PlannedActionIntent.SKIP,
                                        kind="network", name=net.name))

        for subnet in spec.subnets:
            parent_vpc = vpc_by_name.get(subnet.network, None)
            if parent_vpc is None:
                actions.append(_action(intent=PlannedActionIntent.CREATE,
                                        kind="subnet", name=subnet.name))
                continue
            existing_subnets = self._client.subnets.list(
                vpc_id=parent_vpc.id, aspects=aspects,
            )
            found = self._find_owned(records=existing_subnets, run_id=run_id,
                                     resource_name=subnet.name)
            if found is None:
                actions.append(_action(intent=PlannedActionIntent.CREATE,
                                        kind="subnet", name=subnet.name))
            else:
                actions.append(_action(intent=PlannedActionIntent.SKIP,
                                        kind="subnet", name=subnet.name))

        for sg in spec.security_groups:
            parent_vpc = vpc_by_name.get(sg.network, None)
            if parent_vpc is None:
                actions.append(_action(intent=PlannedActionIntent.CREATE,
                                        kind="sg", name=sg.name))
                continue
            existing_sgs = self._client.security_groups.list(
                vpc_id=parent_vpc.id, aspects=aspects,
            )
            found = self._find_owned(records=existing_sgs, run_id=run_id,
                                     resource_name=sg.name)
            if found is None:
                actions.append(_action(intent=PlannedActionIntent.CREATE,
                                        kind="sg", name=sg.name))
            else:
                actions.append(_action(intent=PlannedActionIntent.SKIP,
                                        kind="sg", name=sg.name))

        existing_keys = self._client.ssh_keys.list(aspects=aspects)
        for kp in spec.keypairs:
            found: Optional[Any] = None
            for key in existing_keys:
                if key.name == kp.name:
                    found = key
                    break
            if found is None:
                actions.append(_action(intent=PlannedActionIntent.CREATE,
                                        kind="keypair", name=kp.name))
            else:
                actions.append(_action(intent=PlannedActionIntent.SKIP,
                                        kind="keypair", name=kp.name))

        existing_vms = self._client.vms.list(project_id=spec.parent_id,
                                             aspects=aspects)
        for inst in spec.instances:
            found = self._find_owned(records=existing_vms, run_id=run_id,
                                     resource_name=inst.name)
            if found is None:
                actions.append(_action(intent=PlannedActionIntent.CREATE,
                                        kind="instance", name=inst.name))
            elif self._instance_drifted(existing=found, desired=inst,
                                        resolver=self._resolver):
                actions.append(_action(
                    intent=PlannedActionIntent.UPDATE, kind="instance",
                    name=inst.name,
                    diff={"note": "platform/preset drift — recreate"},
                ))
            else:
                actions.append(_action(intent=PlannedActionIntent.SKIP,
                                        kind="instance", name=inst.name))

        existing_disks = self._client.disks.list(project_id=spec.parent_id,
                                                 aspects=aspects)
        for vol in spec.volumes:
            found = self._find_owned(records=existing_disks, run_id=run_id,
                                     resource_name=vol.name)
            if found is None:
                actions.append(_action(intent=PlannedActionIntent.CREATE,
                                        kind="volume", name=vol.name))
            else:
                actions.append(_action(intent=PlannedActionIntent.SKIP,
                                        kind="volume", name=vol.name))

        for bucket in spec.buckets:
            actions.append(_action(intent=PlannedActionIntent.CREATE,
                                    kind="bucket", name=bucket.name))

        for sfs in spec.shared_filesystems:
            actions.append(_action(intent=PlannedActionIntent.SKIP,
                                    kind="shared_filesystem", name=sfs.name,
                                    diff={"note": "attach-only in v1"}))

        for record in spec.dns_records:
            actions.append(_action(intent=PlannedActionIntent.SKIP,
                                    kind="dns", name=record.name,
                                    diff={"note": "DNS deferred to v1.5"}))

        rtnval = ProvisioningPlan(actions=actions)
        return rtnval

    @staticmethod
    def _instance_drifted(*, existing: Any, desired: Any,
                          resolver: Any) -> bool:
        """
            Return whether an existing VM has drifted from the desired spec.

            The desired preset is resolved through the same resolver the
            apply stage uses (accelerator catalog when GPUs are declared,
            size hint otherwise); preset drift forces an UPDATE-by-recreate.

            :param existing: The existing NebiusVm record.
            :param desired: The desired CloudInstance.
            :param resolver: The NebiusResolver.

            :returns: ``True`` when the instance has drifted.
        """
        existing_preset = getattr(existing, "preset", None)
        if existing_preset is None:
            rtnval = False
            return rtnval

        try:
            desired_preset = resolver.size_to_preset(
                size_hint=desired.size, accelerators=desired.accelerators,
                interconnect=desired.interconnect,
            )
        except Exception:
            rtnval = False
            return rtnval

        rtnval = (existing_preset != desired_preset)
        return rtnval
