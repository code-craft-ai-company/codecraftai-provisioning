"""
    .. module:: rpplanbuilder
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: RpPlanBuilder — diffs a RunpodWorkloadSpec against the live
        RunPod account and emits a ProvisioningPlan.

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

from automojo.provisioning.venues.runpod.rpnaming import pod_name, volume_name
from automojo.provisioning.venues.runpod.rpresolver import RpResolver


class RpPlanBuilder:
    """
        Builds a :class:`ProvisioningPlan` for a :class:`RunpodWorkloadSpec`.

        Every Pod and Network Volume is keyed by its
        ``<name>-<run-id-short>`` prefix. A resource that is absent yields
        CREATE; a resource present with a matching GPU type and template
        yields SKIP; a resource present with a drifted GPU type yields
        UPDATE (RunPod cannot mutate a pod in place, so an UPDATE is realised
        by the apply stage as a terminate-and-recreate).
    """

    def __init__(self, *, resolver: Optional[RpResolver] = None) -> None:
        """
            Construct an :class:`RpPlanBuilder`.

            :param resolver: Optional :class:`RpResolver`; a default instance
                is created when omitted.

            :returns: ``None``.
        """
        self._resolver = resolver if resolver is not None else RpResolver()
        return

    def plan(self, *, spec: Any, client: Any) -> ProvisioningPlan:
        """
            Build the provisioning plan.

            :param spec: The :class:`RunpodWorkloadSpec`.
            :param client: The RunPod interop client (or a mock).

            :returns: A :class:`ProvisioningPlan`.
        """
        run_short = spec.run_id_short

        existing_pods = self._index_pods(client=client)
        existing_volumes = self._index_volumes(client=client)

        actions: List[PlannedAction] = []

        for volume_request in spec.network_volumes:
            base = volume_request.get("name", "volume")
            name = volume_name(volume_name_base=base, run_id_short=run_short)
            intent = PlannedActionIntent.SKIP
            if name not in existing_volumes:
                intent = PlannedActionIntent.CREATE
            actions.append(PlannedAction(intent=intent,
                                         resource_kind="NetworkVolume",
                                         resource_name=name))

        all_workloads = list(spec.jobs) + list(spec.services)
        for workload in all_workloads:
            name = pod_name(workload_name=workload.name,
                            run_id_short=run_short)
            intent = self._pod_intent(workload=workload, name=name,
                                      existing_pods=existing_pods)
            actions.append(PlannedAction(intent=intent, resource_kind="Pod",
                                         resource_name=name))

        rtnval = ProvisioningPlan(actions=actions)
        return rtnval

    def _pod_intent(self, *, workload: Any, name: str,
                    existing_pods: Dict[str, Any]) -> PlannedActionIntent:
        """
            Decide the planned intent for a single pod.

            :param workload: The workload backing the pod.
            :param name: The composed pod name.
            :param existing_pods: The pod index keyed by name.

            :returns: The :class:`PlannedActionIntent`.
        """
        existing = existing_pods.get(name)
        if existing is None:
            rtnval = PlannedActionIntent.CREATE
            return rtnval

        desired_gpu = self._resolver.gpu_type_for_workload(workload=workload)
        live_gpu = getattr(existing, "gpu_type_id", "")
        if desired_gpu is not None and desired_gpu != live_gpu:
            rtnval = PlannedActionIntent.UPDATE
            return rtnval

        rtnval = PlannedActionIntent.SKIP
        return rtnval

    def _index_pods(self, *, client: Any) -> Dict[str, Any]:
        """
            Build a name-keyed index of the live RunPod pods.

            :param client: The RunPod interop client.

            :returns: A dictionary mapping pod name to pod record.
        """
        rtnval: Dict[str, Any] = {}
        for pod in client.list_pods():
            rtnval[pod.name] = pod
        return rtnval

    def _index_volumes(self, *, client: Any) -> Dict[str, Any]:
        """
            Build a name-keyed index of the live RunPod network volumes.

            :param client: The RunPod interop client.

            :returns: A dictionary mapping volume name to volume record.
        """
        rtnval: Dict[str, Any] = {}
        for volume in client.list_network_volumes():
            rtnval[volume.name] = volume
        return rtnval


__all__ = ["RpPlanBuilder"]
