"""
    .. module:: hvplanbuilder
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: HvPlanBuilder — computes the CREATE / SKIP / UPDATE dry-run
        plan for the Hyper-V venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List

from automojo.provisioning.model.cloud.plannedaction import PlannedAction
from automojo.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)
from automojo.provisioning.model.cloud.provisioningplan import ProvisioningPlan

from automojo.provisioning.venues.hyperv.hvhostconfig import HvHostConfig
from automojo.provisioning.venues.hyperv.hvnotestranslator import (
    HvNotesTranslator
)
from automojo.provisioning.venues.hyperv.hvresolver import HvResolver


class HvPlanBuilder:
    """
        Builds a :class:`ProvisioningPlan` for the Hyper-V venue.

        The plan is computed with read-only ``Get-VMSwitch`` / ``Get-VM`` /
        ``Get-VHD`` calls.  VMs and switches that already exist yield SKIP;
        absent resources yield CREATE; a VM whose resolved processor count
        or memory drifts from the host record yields UPDATE.
    """

    def __init__(self, *, client: Any, host_config: HvHostConfig,
                 resolver: HvResolver,
                 notes: HvNotesTranslator) -> None:
        """
            Construct an HvPlanBuilder.

            :param client: The HypervClient interop client.
            :param host_config: The HvHostConfig for the run.
            :param resolver: The HvResolver.
            :param notes: The HvNotesTranslator.
        """
        self._client: Any = client
        self._host_config: HvHostConfig = host_config
        self._resolver: HvResolver = resolver
        self._notes: HvNotesTranslator = notes
        return

    def plan(self, *, spec: Any, run_id: str, aspects: Any) -> ProvisioningPlan:
        """
            Compute the CREATE / SKIP / UPDATE plan for a spec.

            :param spec: The HypervSpec resource bundle.
            :param run_id: The provisioning run identifier.
            :param aspects: The AspectsRunner passed to interop calls.

            :returns: A ProvisioningPlan.
        """
        actions: List[PlannedAction] = []

        if spec is None:
            rtnval = ProvisioningPlan(actions=actions)
            return rtnval

        existing_switches = self._index_switches(aspects=aspects)
        for net in spec.networks:
            existing = existing_switches.get(net.name, None)
            if existing is None:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="network", resource_name=net.name))
            else:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="network", resource_name=net.name))

        existing_vms = self._index_vms(aspects=aspects)
        for inst in spec.instances:
            existing = existing_vms.get(inst.name, None)
            if existing is None:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="instance", resource_name=inst.name))
                continue

            hardware = self._resolver.size_to_hardware(size_hint=inst.size)
            cpu_drift = existing.processor_count != hardware.processor_count
            mem_drift = (
                existing.memory_startup_bytes != hardware.memory_startup_bytes
            )
            if cpu_drift is True or mem_drift is True:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.UPDATE,
                    resource_kind="instance", resource_name=inst.name,
                    diff={
                        "before": {
                            "processor_count": existing.processor_count,
                            "memory_startup_bytes":
                                existing.memory_startup_bytes,
                        },
                        "after": {
                            "processor_count": hardware.processor_count,
                            "memory_startup_bytes":
                                hardware.memory_startup_bytes,
                        },
                        "note": "VM hardware drift: Set-VMProcessor/Memory",
                    }))
            else:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="instance", resource_name=inst.name))

        for vol in spec.volumes:
            vhdx_path = self._volume_path(volume_name=vol.name)
            existing_vhdx = self._client.vhdx.get_vhdx(path=vhdx_path,
                                                       aspects=aspects)
            if existing_vhdx is None:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="volume", resource_name=vol.name))
            else:
                actions.append(PlannedAction(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="volume", resource_name=vol.name))

        rtnval = ProvisioningPlan(actions=actions)
        return rtnval

    def _volume_path(self, *, volume_name: str) -> str:
        """
            Resolve the host VHDX path for an additional data volume.

            :param volume_name: The neutral volume name.

            :returns: The host VHDX path string.
        """
        rtnval = self._resolver._join(root=self._host_config.vhd_root,
                                      leaf="{}-data.vhdx".format(volume_name))
        return rtnval

    def _index_switches(self, *, aspects: Any) -> Dict[str, Any]:
        """
            Index existing virtual switches by name.

            :param aspects: The AspectsRunner.

            :returns: A name -> HypervVirtualSwitch dict.
        """
        rtnval: Dict[str, Any] = {}
        for switch in self._client.switches.list_switches(aspects=aspects):
            rtnval[switch.name] = switch
        return rtnval

    def _index_vms(self, *, aspects: Any) -> Dict[str, Any]:
        """
            Index existing VMs by name.

            :param aspects: The AspectsRunner.

            :returns: A name -> HypervVm dict.
        """
        rtnval: Dict[str, Any] = {}
        for vm in self._client.vms.list_vms(aspects=aspects):
            rtnval[vm.name] = vm
        return rtnval
