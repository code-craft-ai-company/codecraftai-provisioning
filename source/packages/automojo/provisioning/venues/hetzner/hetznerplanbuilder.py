"""
    .. module:: hetznerplanbuilder
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: HetznerPlanBuilder — read-only CREATE/SKIP/UPDATE/DELETE planner.

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
from automojo.provisioning.venues.hetzner.hetznerlabeltranslator import (
    HetznerLabelTranslator
)
from automojo.provisioning.venues.hetzner.hetznerresolver import (
    HetznerResolver
)
from automojo.provisioning.venues.hetzner.hetznerspec import HetznerSpec


def _labels_of(obj: Any) -> Dict[str, str]:
    """
        Read the ``labels`` dict off an hcloud-shaped object.

        :param obj: An hcloud resource object.

        :returns: The labels dict (empty when absent).
    """
    labels = getattr(obj, "labels", None)
    if labels is None:
        rtnval: Dict[str, str] = {}
        return rtnval
    rtnval = dict(labels)
    return rtnval


class HetznerPlanBuilder:
    """
        Builds a :class:`ProvisioningPlan` by reading live Hetzner state.

        Reads use ``get_by_name`` on each Hetzner resource collection.  A
        live resource whose owner labels match the run and whose mutable
        attributes equal the desired state yields SKIP; a mutable-attribute
        drift yields UPDATE; absence yields CREATE.  Server-type changes are
        UPDATE-by-recreate.
    """

    def __init__(self, *, client: Any) -> None:
        """
            Construct a HetznerPlanBuilder.

            :param client: An hcloud Client (or mock).
        """
        self._client: Any = client
        return

    def plan(self, *, spec: Optional[HetznerSpec],
             run_id: str, aspects: Any) -> ProvisioningPlan:
        """
            Compute a CREATE/SKIP/UPDATE plan against live Hetzner state.

            :param spec: The HetznerSpec (None yields an empty plan).
            :param run_id: The provisioning run identifier.
            :param aspects: ProvisioningAspects.

            :returns: A ProvisioningPlan.
        """
        actions: List[PlannedAction] = []

        if spec is None:
            rtnval = ProvisioningPlan(actions=actions)
            return rtnval

        self._plan_networks(spec=spec, run_id=run_id, actions=actions)
        self._plan_firewalls(spec=spec, run_id=run_id, actions=actions)
        self._plan_keypairs(spec=spec, run_id=run_id, actions=actions)
        self._plan_servers(spec=spec, run_id=run_id, actions=actions)
        self._plan_volumes(spec=spec, run_id=run_id, actions=actions)
        self._plan_dns(spec=spec, actions=actions)

        for lb in spec.load_balancers:
            actions.append(PlannedAction(
                intent=PlannedActionIntent.SKIP,
                resource_kind="lb", resource_name=lb.name,
                diff={"note": "Hetzner load balancer apply is deferred "
                              "to v1.5."},
            ))

        rtnval = ProvisioningPlan(actions=actions)
        return rtnval

    def _plan_networks(self, *, spec: HetznerSpec, run_id: str,
                       actions: List[PlannedAction]) -> None:
        """
            Append network actions to the plan.

            :param spec: The HetznerSpec.
            :param run_id: Run identifier.
            :param actions: Action list being built.
        """
        for net in spec.networks:
            existing = self._client.networks.get_by_name(name=net.name)
            if existing is None or not HetznerLabelTranslator.belongs_to_run(
                    labels=_labels_of(existing), run_id=run_id):
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="network", resource_name=net.name))
                continue
            if getattr(existing, "ip_range", None) == net.cidr:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="network", resource_name=net.name))
            else:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.UPDATE,
                    resource_kind="network", resource_name=net.name,
                    diff={"before": {"cidr": getattr(existing,
                                                     "ip_range", "")},
                          "after": {"cidr": net.cidr}}))
        return

    def _plan_firewalls(self, *, spec: HetznerSpec, run_id: str,
                        actions: List[PlannedAction]) -> None:
        """
            Append firewall actions to the plan.

            :param spec: The HetznerSpec.
            :param run_id: Run identifier.
            :param actions: Action list being built.
        """
        for sg in spec.security_groups:
            existing = self._client.firewalls.get_by_name(name=sg.name)
            if existing is None or not HetznerLabelTranslator.belongs_to_run(
                    labels=_labels_of(existing), run_id=run_id):
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="security_group",
                    resource_name=sg.name))
            else:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="security_group",
                    resource_name=sg.name))
        return

    def _plan_keypairs(self, *, spec: HetznerSpec, run_id: str,
                       actions: List[PlannedAction]) -> None:
        """
            Append SSH-key actions to the plan.

            :param spec: The HetznerSpec.
            :param run_id: Run identifier.
            :param actions: Action list being built.
        """
        for kp in spec.keypairs:
            existing = self._client.ssh_keys.get_by_name(name=kp.name)
            if existing is None:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="keypair", resource_name=kp.name))
            else:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="keypair", resource_name=kp.name))
        return

    def _plan_servers(self, *, spec: HetznerSpec, run_id: str,
                      actions: List[PlannedAction]) -> None:
        """
            Append server actions to the plan.

            :param spec: The HetznerSpec.
            :param run_id: Run identifier.
            :param actions: Action list being built.
        """
        for inst in spec.instances:
            existing = self._client.servers.get_by_name(name=inst.name)
            if existing is None or not HetznerLabelTranslator.belongs_to_run(
                    labels=_labels_of(existing), run_id=run_id):
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="instance", resource_name=inst.name))
                continue

            accel_models: List[str] = []
            if inst.accelerators is not None:
                for entry in inst.accelerators:
                    accel_models.append(entry.model)
            desired_type = HetznerResolver.size_to_type(
                size_hint=inst.size, accelerators=accel_models)
            live_type = self._server_type_name(server=existing)
            if live_type == desired_type:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="instance", resource_name=inst.name))
            else:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.UPDATE,
                    resource_kind="instance", resource_name=inst.name,
                    diff={"before": {"server_type": live_type},
                          "after": {"server_type": desired_type},
                          "note": "Server type change is UPDATE-by-"
                                  "recreate."}))
        return

    def _plan_volumes(self, *, spec: HetznerSpec, run_id: str,
                      actions: List[PlannedAction]) -> None:
        """
            Append volume actions to the plan.

            :param spec: The HetznerSpec.
            :param run_id: Run identifier.
            :param actions: Action list being built.
        """
        for vol in spec.volumes:
            existing = self._client.volumes.get_by_name(name=vol.name)
            if existing is None or not HetznerLabelTranslator.belongs_to_run(
                    labels=_labels_of(existing), run_id=run_id):
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="volume", resource_name=vol.name))
            elif getattr(existing, "size", None) == vol.size_gb:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="volume", resource_name=vol.name))
            else:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.UPDATE,
                    resource_kind="volume", resource_name=vol.name,
                    diff={"before": {"size_gb": getattr(existing,
                                                        "size", 0)},
                          "after": {"size_gb": vol.size_gb}}))
        return

    def _plan_dns(self, *, spec: HetznerSpec,
                  actions: List[PlannedAction]) -> None:
        """
            Append DNS record actions to the plan.

            :param spec: The HetznerSpec.
            :param actions: Action list being built.
        """
        for record in spec.dns_records:
            actions.append(PlannedAction(
                intent=PlannedActionIntent.CREATE,
                resource_kind="dns", resource_name=record.name))
        return

    @classmethod
    def _server_type_name(cls, *, server: Any) -> Optional[str]:
        """
            Extract the server-type slug from a live server object.

            :param server: An hcloud-shaped server object.

            :returns: The server-type name, or None.
        """
        server_type = getattr(server, "server_type", None)
        if server_type is None:
            rtnval: Optional[str] = None
            return rtnval
        rtnval = getattr(server_type, "name", None)
        return rtnval
