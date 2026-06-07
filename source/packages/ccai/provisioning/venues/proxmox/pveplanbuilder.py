"""
    .. module:: pveplanbuilder
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: PvePlanBuilder — computes the CREATE/SKIP/UPDATE plan for
               the Proxmox VE venue provisioner.

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
from ccai.provisioning.venues.proxmox.pvenaming import (
    has_run_id_tag, vm_name_for
)
from ccai.provisioning.venues.proxmox.pveresolver import PveResolver
from ccai.provisioning.venues.proxmox.proxmoxspec import ProxmoxSpec


class PvePlanBuilder:
    """
        Builds a :class:`ProvisioningPlan` for a :class:`ProxmoxSpec`.

        Plan reads venue state through the Proxmox interop client and emits
        one :class:`PlannedAction` per resource: CREATE when absent, SKIP
        when already-realised in shape, and UPDATE when the VM hardware
        drifts from the spec.  Reads filter VM listings by the
        ``codecraftai-run-id`` Proxmox tag.
    """

    def __init__(self, *, client: Any, resolver: PveResolver) -> None:
        """
            Construct a PvePlanBuilder.

            :param client: The Proxmox interop client.
            :param resolver: The :class:`PveResolver`.
        """
        self._client = client
        self._resolver = resolver
        return

    def plan(self, *, spec: Optional[ProxmoxSpec], run_id: str,
             aspects: Any) -> ProvisioningPlan:
        """
            Compute the CREATE/SKIP/UPDATE plan.

            :param spec: The :class:`ProxmoxSpec`, or ``None``.
            :param run_id: The provisioning run id.
            :param aspects: Behaviour control passed to the interop client.

            :returns: A :class:`ProvisioningPlan`.
        """
        actions: List[PlannedAction] = []

        if spec is None:
            rtnval = ProvisioningPlan(actions=actions)
            return rtnval

        self._plan_networks(spec=spec, run_id=run_id, aspects=aspects,
                            actions=actions)
        self._plan_security_groups(spec=spec, actions=actions)
        self._plan_vms(spec=spec, run_id=run_id, aspects=aspects,
                       actions=actions)
        self._plan_volumes(spec=spec, actions=actions)

        rtnval = ProvisioningPlan(actions=actions)
        return rtnval

    def _plan_networks(self, *, spec: ProxmoxSpec, run_id: str, aspects: Any,
                       actions: List[PlannedAction]) -> None:
        """
            Append network CREATE/SKIP actions.

            :param spec: The :class:`ProxmoxSpec`.
            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.
            :param actions: The action accumulator.

            :returns: ``None``.
        """
        # `run_id` retained for interface uniformity; bridges/VNets carry
        # no per-run tag, so name identity is the ownership signal.
        _ = run_id

        live_names: List[str] = []
        for network in spec.networks:
            node = self._resolver.default_node
            if node is None:
                continue
            live = self._client.networks.list_node_networks(
                node_name=node, aspects=aspects
            )
            for entry in live:
                live_names.append(entry.iface)
            break

        for network in spec.networks:
            if network.name in live_names:
                intent = PlannedActionIntent.SKIP
            else:
                intent = PlannedActionIntent.CREATE
            actions.append(PlannedAction(intent=intent,
                                         resource_kind="network",
                                         resource_name=network.name))
        return

    def _plan_security_groups(self, *, spec: ProxmoxSpec,
                              actions: List[PlannedAction]) -> None:
        """
            Append security-group CREATE actions.

            :param spec: The :class:`ProxmoxSpec`.
            :param actions: The action accumulator.

            :returns: ``None``.
        """
        for sg in spec.security_groups:
            actions.append(PlannedAction(
                intent=PlannedActionIntent.CREATE,
                resource_kind="security_group",
                resource_name=sg.name,
            ))
        return

    def _plan_vms(self, *, spec: ProxmoxSpec, run_id: str, aspects: Any,
                  actions: List[PlannedAction]) -> None:
        """
            Append VM CREATE/SKIP/UPDATE actions.

            :param spec: The :class:`ProxmoxSpec`.
            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.
            :param actions: The action accumulator.

            :returns: ``None``.
        """
        live_by_name = self._live_vms_by_name(run_id=run_id, aspects=aspects)

        for inst in spec.instances:
            venue_name = vm_name_for(spec_name=inst.name, run_id=run_id)
            existing = live_by_name.get(venue_name, None)

            if existing is None:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="instance",
                    resource_name=inst.name,
                ))
                continue

            hardware = self._resolver.size_to_hardware(size_hint=inst.size)
            drifted = False
            diff: Dict[str, Any] = {}
            if existing.cpus is not None:
                if int(existing.cpus) != hardware.cores:
                    drifted = True
                    diff["cores"] = {"before": existing.cpus,
                                     "after": hardware.cores}
            if existing.maxmem is not None:
                desired_bytes = hardware.memory_mb * 1024 * 1024
                if int(existing.maxmem) != desired_bytes:
                    drifted = True
                    diff["memory"] = {"before": existing.maxmem,
                                      "after": desired_bytes}

            if drifted is True:
                diff["note"] = ("Proxmox VM vCPU/memory drift; the interop "
                                "client exposes no in-place hardware "
                                "reconfigure, so UPDATE is realised "
                                "by-recreate (stop + destroy + re-clone) "
                                "and gated behind aspects.confirm.")
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.UPDATE,
                    resource_kind="instance",
                    resource_name=inst.name,
                    diff=diff,
                ))
            else:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="instance",
                    resource_name=inst.name,
                ))
        return

    def _plan_volumes(self, *, spec: ProxmoxSpec,
                      actions: List[PlannedAction]) -> None:
        """
            Append storage-volume CREATE actions.

            :param spec: The :class:`ProxmoxSpec`.
            :param actions: The action accumulator.

            :returns: ``None``.
        """
        for volume in spec.volumes:
            actions.append(PlannedAction(
                intent=PlannedActionIntent.CREATE,
                resource_kind="volume",
                resource_name=volume.name,
            ))
        return

    def _live_vms_by_name(self, *, run_id: str,
                          aspects: Any) -> Dict[str, Any]:
        """
            List run-owned VMs across every cluster node, keyed by name.

            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.

            :returns: A dict of venue-side VM name to VM-status record.
        """
        rtnval: Dict[str, Any] = {}
        for node in self._client.nodes.list(aspects=aspects):
            vms = self._client.qemu.list_vms(node_name=node.name,
                                             aspects=aspects)
            for vm in vms:
                if has_run_id_tag(tags=vm.tags, run_id=run_id) is not True:
                    continue
                if vm.name is None:
                    continue
                rtnval[vm.name] = vm
        return rtnval
