"""
    .. module:: linodeplanbuilder
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: LinodePlanBuilder — computes the CREATE/SKIP/UPDATE plan for a
               LinodeSpec by reading run-id-tagged Linode resources.

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
from automojo.provisioning.venues.linode.linodereader import LinodeReader
from automojo.provisioning.venues.linode.linoderesolver import LinodeResolver
from automojo.provisioning.venues.linode.linodespec import LinodeSpec


class LinodePlanBuilder:
    """
        Builder that walks a :class:`LinodeSpec` and produces a
        :class:`ProvisioningPlan` of CREATE / SKIP / UPDATE actions.

        Reads are tag-filtered listings against the Linode SDK via the
        :class:`LinodeReader`; no mutation is performed.
    """

    def __init__(self, *, reader: LinodeReader,
                 resolver: LinodeResolver) -> None:
        """
            Construct a LinodePlanBuilder.

            :param reader: A LinodeReader bound to a client + run id.
            :param resolver: A LinodeResolver.
        """
        self._reader: LinodeReader = reader
        self._resolver: LinodeResolver = resolver
        return

    def _action(self, *, intent: PlannedActionIntent, kind: str,
                name: str,
                diff: Optional[Dict[str, Any]] = None) -> PlannedAction:
        """
            Build a single PlannedAction.

            :param intent: The PlannedActionIntent.
            :param kind: Resource kind string.
            :param name: Resource name.
            :param diff: Optional diff payload.

            :returns: A PlannedAction.
        """
        rtnval = PlannedAction(intent=intent, resource_kind=kind,
                               resource_name=name, diff=diff)
        return rtnval

    def plan(self, *, spec: Optional[LinodeSpec], run_id: str
             ) -> ProvisioningPlan:
        """
            Compute the provisioning plan for a LinodeSpec.

            :param spec: The LinodeSpec, or None.
            :param run_id: The provisioning run identifier.

            :returns: A ProvisioningPlan.
        """
        actions: List[PlannedAction] = []
        if spec is None:
            rtnval = ProvisioningPlan(actions=actions)
            return rtnval

        for net in spec.networks:
            existing = self._reader.find_vpc(name=net.name)
            if existing is None:
                actions.append(self._action(
                    intent=PlannedActionIntent.CREATE,
                    kind="network", name=net.name,
                ))
            else:
                actions.append(self._action(
                    intent=PlannedActionIntent.SKIP,
                    kind="network", name=net.name,
                ))

        for subnet in spec.subnets:
            existing = self._reader.find_subnet(name=subnet.name)
            if existing is None:
                actions.append(self._action(
                    intent=PlannedActionIntent.CREATE,
                    kind="subnet", name=subnet.name,
                ))
            else:
                actions.append(self._action(
                    intent=PlannedActionIntent.SKIP,
                    kind="subnet", name=subnet.name,
                ))

        for sg in spec.security_groups:
            existing = self._reader.find_firewall(name=sg.name)
            if existing is None:
                actions.append(self._action(
                    intent=PlannedActionIntent.CREATE,
                    kind="sg", name=sg.name,
                ))
            else:
                actions.append(self._action(
                    intent=PlannedActionIntent.SKIP,
                    kind="sg", name=sg.name,
                ))

        for kp in spec.keypairs:
            existing = self._reader.find_sshkey(name=kp.name)
            if existing is None:
                actions.append(self._action(
                    intent=PlannedActionIntent.CREATE,
                    kind="keypair", name=kp.name,
                ))
            else:
                actions.append(self._action(
                    intent=PlannedActionIntent.SKIP,
                    kind="keypair", name=kp.name,
                ))

        for inst in spec.instances:
            existing = self._reader.find_instance(name=inst.name)
            if existing is None:
                actions.append(self._action(
                    intent=PlannedActionIntent.CREATE,
                    kind="instance", name=inst.name,
                ))
            else:
                desired_type = self._resolver.size_to_type(
                    size_hint=inst.size,
                    accelerators=self._accelerator_models(instance=inst),
                )
                current_type = getattr(existing, "type", None)
                current_type_id = getattr(current_type, "id", current_type)
                if current_type_id is not None \
                        and current_type_id != desired_type:
                    actions.append(self._action(
                        intent=PlannedActionIntent.UPDATE,
                        kind="instance", name=inst.name,
                        diff={"before": {"type": current_type_id},
                              "after": {"type": desired_type},
                              "strategy": "resize"},
                    ))
                else:
                    actions.append(self._action(
                        intent=PlannedActionIntent.SKIP,
                        kind="instance", name=inst.name,
                    ))

        for vol in spec.volumes:
            existing = self._reader.find_volume(name=vol.name)
            if existing is None:
                actions.append(self._action(
                    intent=PlannedActionIntent.CREATE,
                    kind="volume", name=vol.name,
                ))
            else:
                actions.append(self._action(
                    intent=PlannedActionIntent.SKIP,
                    kind="volume", name=vol.name,
                ))

        for bucket in spec.buckets:
            existing = self._reader.find_bucket(name=bucket.name)
            if existing is None:
                actions.append(self._action(
                    intent=PlannedActionIntent.CREATE,
                    kind="bucket", name=bucket.name,
                ))
            else:
                actions.append(self._action(
                    intent=PlannedActionIntent.SKIP,
                    kind="bucket", name=bucket.name,
                ))

        for record in spec.dns_records:
            existing = self._reader.find_dns_record(zone=record.zone,
                                                    name=record.name)
            if existing is None:
                actions.append(self._action(
                    intent=PlannedActionIntent.CREATE,
                    kind="dns", name=record.name,
                ))
            else:
                actions.append(self._action(
                    intent=PlannedActionIntent.SKIP,
                    kind="dns", name=record.name,
                ))

        for lb in spec.load_balancers:
            actions.append(self._action(
                intent=PlannedActionIntent.SKIP,
                kind="lb", name=lb.name,
                diff={"note": "NodeBalancer apply is deferred to v1.5."},
            ))

        rtnval = ProvisioningPlan(actions=actions)
        return rtnval

    @staticmethod
    def _accelerator_models(*, instance: Any) -> List[str]:
        """
            Extract the neutral accelerator model strings from an instance.

            :param instance: A CloudInstance.

            :returns: A list of model strings (possibly empty).
        """
        accelerators = instance.accelerators if instance.accelerators is not None else []
        out: List[str] = []
        for entry in accelerators:
            out.append(entry.model)
        rtnval = out
        return rtnval
