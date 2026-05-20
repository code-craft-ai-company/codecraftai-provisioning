"""
    .. module:: vultrplanbuilder
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: VultrPlanBuilder — computes the CREATE/SKIP/UPDATE plan.

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
from automojo.provisioning.venues.vultr.vultrclient import VultrClient
from automojo.provisioning.venues.vultr.vultrresources import find_named
from automojo.provisioning.venues.vultr.vultrspec import VultrSpec


class VultrPlanBuilder:
    """
        Builds a :class:`ProvisioningPlan` for a :class:`VultrSpec`.

        Performs read-only Vultr listings filtered by owner tag and emits a
        :class:`PlannedAction` per declared resource.  No mutation is done.
    """

    def __init__(self, *, client: VultrClient) -> None:
        """
            Construct a VultrPlanBuilder.

            :param client: A VultrClient for read-only listings.
        """
        self._client: VultrClient = client
        return

    def _action(self, *, intent: PlannedActionIntent, kind: str, name: str,
                diff: Optional[Dict[str, Any]] = None) -> PlannedAction:
        """
            Build a PlannedAction entry.

            :param intent: The PlannedActionIntent.
            :param kind: The resource kind string.
            :param name: The resource name.
            :param diff: Optional diff payload.

            :returns: A PlannedAction.
        """
        rtnval = PlannedAction(intent=intent, resource_kind=kind,
                               resource_name=name, diff=diff)
        return rtnval

    def _plan_collection(self, *, actions: List[PlannedAction], kind: str,
                         path: str, collection_key: str, run_id: str,
                         entries: List[Any]) -> None:
        """
            Append CREATE/SKIP actions for a simple resource collection.

            :param actions: The action list to append to.
            :param kind: The resource kind string.
            :param path: The Vultr list endpoint path.
            :param collection_key: The list collection key.
            :param run_id: The provisioning run identifier.
            :param entries: The neutral resource entries to plan.
        """
        for entry in entries:
            existing = find_named(client=self._client, path=path,
                                  collection_key=collection_key,
                                  run_id=run_id, name=entry.name)
            if existing is None:
                actions.append(self._action(
                    intent=PlannedActionIntent.CREATE, kind=kind,
                    name=entry.name,
                ))
            else:
                actions.append(self._action(
                    intent=PlannedActionIntent.SKIP, kind=kind,
                    name=entry.name,
                ))
        return

    def plan(self, *, spec: Optional[VultrSpec], run_id: str
             ) -> ProvisioningPlan:
        """
            Compute a CREATE/SKIP/UPDATE plan for the spec.

            :param spec: The VultrSpec (may be None).
            :param run_id: The provisioning run identifier.

            :returns: A ProvisioningPlan.
        """
        actions: List[PlannedAction] = []
        if spec is None:
            rtnval = ProvisioningPlan(actions=actions)
            return rtnval

        self._plan_collection(actions=actions, kind="network", path="/vpc2",
                              collection_key="vpcs", run_id=run_id,
                              entries=spec.networks)
        self._plan_collection(actions=actions, kind="sg", path="/firewalls",
                              collection_key="firewall_groups", run_id=run_id,
                              entries=spec.security_groups)
        self._plan_collection(actions=actions, kind="keypair",
                              path="/ssh-keys", collection_key="ssh_keys",
                              run_id=run_id, entries=spec.keypairs)
        self._plan_collection(actions=actions, kind="instance",
                              path="/instances", collection_key="instances",
                              run_id=run_id, entries=spec.instances)
        self._plan_collection(actions=actions, kind="volume", path="/blocks",
                              collection_key="blocks", run_id=run_id,
                              entries=spec.volumes)
        self._plan_collection(actions=actions, kind="bucket",
                              path="/object-storage",
                              collection_key="object_storages",
                              run_id=run_id, entries=spec.buckets)

        # DNS records have no owner-tag read-side; emit CREATE every plan.
        for record in spec.dns_records:
            actions.append(self._action(
                intent=PlannedActionIntent.CREATE, kind="dns",
                name=record.name,
            ))

        # Load balancers are deferred to a future Vultr LB stub.
        for lb in spec.load_balancers:
            actions.append(self._action(
                intent=PlannedActionIntent.SKIP, kind="lb", name=lb.name,
                diff={"note": "Vultr load balancer apply is deferred."},
            ))

        rtnval = ProvisioningPlan(actions=actions)
        return rtnval
