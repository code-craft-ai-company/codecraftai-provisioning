"""
    .. module:: lvplanbuilder
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: LvPlanBuilder — computes the CREATE/SKIP/UPDATE plan for the
               libvirt venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from ccai.provisioning.model.cloud.plannedaction import PlannedAction
from ccai.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)
from ccai.provisioning.model.cloud.provisioningplan import ProvisioningPlan
from ccai.provisioning.venues.libvirt.libvirtspec import LibvirtSpec
from ccai.provisioning.venues.libvirt.libvirtvenueconfig import (
    LibvirtVenueConfig
)
from ccai.provisioning.venues.libvirt.lvdomainxmlbuilder import (
    LvDomainXmlBuilder
)
from ccai.provisioning.venues.libvirt.lvnaming import resource_name_for


class LvPlanBuilder:
    """
        Builds a :class:`ProvisioningPlan` for a :class:`LibvirtSpec`.

        Plan reads venue state through the interop client and emits one
        :class:`PlannedAction` per Network, Volume, and Domain: CREATE
        when the venue-side name is absent, SKIP when already defined in
        shape, and UPDATE when a domain's vCPU / memory drifts from the
        spec.  Plan performs no mutation.
    """

    def __init__(self, *, client: Any, config: LibvirtVenueConfig,
                 domain_builder: Optional[LvDomainXmlBuilder] = None
                 ) -> None:
        """
            Construct an LvPlanBuilder.

            :param client: The libvirt interop client.
            :param config: The :class:`LibvirtVenueConfig`.
            :param domain_builder: Optional :class:`LvDomainXmlBuilder`;
                defaults to a fresh instance.
        """
        self._client = client
        self._config = config
        if domain_builder is not None:
            self._domain_builder: LvDomainXmlBuilder = domain_builder
        else:
            self._domain_builder = LvDomainXmlBuilder()
        return

    def plan(self, *, spec: Optional[LibvirtSpec], run_id: str,
             aspects: Any) -> ProvisioningPlan:
        """
            Compute the CREATE/SKIP/UPDATE plan.

            :param spec: The :class:`LibvirtSpec`, or ``None``.
            :param run_id: The provisioning run id.
            :param aspects: Behaviour control passed to the interop
                client.

            :returns: A :class:`ProvisioningPlan`.
        """
        actions: List[PlannedAction] = []

        if spec is None:
            rtnval = ProvisioningPlan(actions=actions)
            return rtnval

        self._plan_networks(spec=spec, run_id=run_id, aspects=aspects,
                            actions=actions)
        self._plan_volumes(spec=spec, run_id=run_id, aspects=aspects,
                           actions=actions)
        self._plan_domains(spec=spec, run_id=run_id, aspects=aspects,
                           actions=actions)

        rtnval = ProvisioningPlan(actions=actions)
        return rtnval

    def _plan_networks(self, *, spec: LibvirtSpec, run_id: str,
                       aspects: Any,
                       actions: List[PlannedAction]) -> None:
        """
            Append the network actions to the plan.

            :param spec: The :class:`LibvirtSpec`.
            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.
            :param actions: The accumulating action list.

            :returns: ``None``.
        """
        live = self._client.networks.list_networks(aspects=aspects)
        live_names: List[str] = []
        for network in live:
            live_names.append(network.name)

        for network in spec.networks:
            venue_name = resource_name_for(spec_name=network.name,
                                           run_id=run_id)
            if venue_name in live_names:
                intent = PlannedActionIntent.SKIP
            else:
                intent = PlannedActionIntent.CREATE
            actions.append(PlannedAction(intent=intent,
                                         resource_kind="network",
                                         resource_name=network.name))
        return

    def _plan_volumes(self, *, spec: LibvirtSpec, run_id: str,
                      aspects: Any,
                      actions: List[PlannedAction]) -> None:
        """
            Append the volume actions to the plan.

            :param spec: The :class:`LibvirtSpec`.
            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.
            :param actions: The accumulating action list.

            :returns: ``None``.
        """
        pool_name = self._config.boot_disk_pool
        live = self._client.volumes.list_volumes(pool_name=pool_name,
                                                 aspects=aspects)
        live_names: List[str] = []
        for volume in live:
            live_names.append(volume.name)

        for volume in spec.volumes:
            venue_name = resource_name_for(spec_name=volume.name,
                                           run_id=run_id)
            if venue_name in live_names:
                intent = PlannedActionIntent.SKIP
            else:
                intent = PlannedActionIntent.CREATE
            actions.append(PlannedAction(intent=intent,
                                         resource_kind="volume",
                                         resource_name=volume.name))
        return

    def _plan_domains(self, *, spec: LibvirtSpec, run_id: str,
                      aspects: Any,
                      actions: List[PlannedAction]) -> None:
        """
            Append the domain actions to the plan.

            :param spec: The :class:`LibvirtSpec`.
            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.
            :param actions: The accumulating action list.

            :returns: ``None``.
        """
        live = self._client.domains.list_domains(aspects=aspects)
        live_by_name: Dict[str, Any] = {}
        for domain in live:
            live_by_name[domain.name] = domain

        for instance in spec.instances:
            venue_name = resource_name_for(spec_name=instance.name,
                                           run_id=run_id)
            existing = live_by_name.get(venue_name, None)

            if existing is None:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="instance",
                    resource_name=instance.name,
                ))
                continue

            sizing = self._domain_builder.resolve_size(size=instance.size)
            desired_vcpus = sizing["vcpus"]
            desired_memory_kib = sizing["memory_mib"] * 1024

            drift = (existing.vcpus != desired_vcpus
                     or existing.memory_kib != desired_memory_kib)
            if drift:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.UPDATE,
                    resource_kind="instance",
                    resource_name=instance.name,
                    diff={"before": {"vcpus": existing.vcpus,
                                     "memory_kib": existing.memory_kib},
                          "after": {"vcpus": desired_vcpus,
                                    "memory_kib": desired_memory_kib},
                          "note": "libvirt vCPU/memory drift; UPDATE is "
                                  "realised by recreate when the guest "
                                  "does not support live edit."},
                ))
            else:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="instance",
                    resource_name=instance.name,
                ))
        return
