"""
    .. module:: rpapplystages
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: RpApplyStages — the ensure-volumes and apply-pods stages of
        the RunPod workload provisioner apply lifecycle.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.interop.runpod.enums.runpodcloudtype import RunpodCloudType
from automojo.interop.runpod.specs.runpodnetworkvolumespec import (
    RunpodNetworkVolumeSpec
)
from automojo.interop.runpod.specs.runpodpodlaunchspec import (
    RunpodPodLaunchSpec
)

from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)

from automojo.provisioning.venues.runpod.rpcontainerstartrenderer import (
    RpContainerStartRenderer
)
from automojo.provisioning.venues.runpod.rpnaming import pod_name, volume_name
from automojo.provisioning.venues.runpod.rpresolver import RpResolver
from automojo.provisioning.venues.runpod.runpodworkloadspec import (
    RUNPOD_TIER_COMMUNITY
)


class RpApplyStages:
    """
        The apply-lifecycle stages of the RunPod workload provisioner.

        :meth:`ensure_network_volumes` realises the declared Network Volumes
        idempotently. :meth:`apply_pods` translates each :class:`WorkloadJob`
        / :class:`WorkloadService` into a RunPod pod, honouring the requested
        Secure vs Community tier and rendering the userspace-Tailscale-aware
        container start script. Both stages are idempotent — the interop
        client's idempotent create / re-discovery semantics mean an apply on
        already-realised resources mutates nothing.
    """

    def __init__(self, *, resolver: Optional[RpResolver] = None,
                 renderer: Optional[RpContainerStartRenderer] = None) -> None:
        """
            Construct an :class:`RpApplyStages`.

            :param resolver: Optional :class:`RpResolver`.
            :param renderer: Optional :class:`RpContainerStartRenderer`.

            :returns: ``None``.
        """
        self._resolver = resolver if resolver is not None else RpResolver()
        self._renderer = renderer
        if self._renderer is None:
            self._renderer = RpContainerStartRenderer()
        return

    def ensure_network_volumes(self, *, spec: Any,
                               client: Any) -> Dict[str, str]:
        """
            Ensure every declared Network Volume exists.

            :param spec: The :class:`RunpodWorkloadSpec`.
            :param client: The RunPod interop client.

            :returns: A dictionary mapping the neutral volume name to the
                realised RunPod volume id.
        """
        run_short = spec.run_id_short

        rtnval: Dict[str, str] = {}
        for volume_request in spec.network_volumes:
            base = volume_request.get("name", "volume")

            existing_id = volume_request.get("existing_id")
            if existing_id is not None:
                rtnval[base] = existing_id
                continue

            size_gb = volume_request.get("size_gb", 50)
            name = volume_name(volume_name_base=base, run_id_short=run_short)
            volume_spec = RunpodNetworkVolumeSpec(
                name=name, size_gb=size_gb,
                data_center_id=spec.data_center_id)
            volume = client.create_network_volume(spec=volume_spec)
            rtnval[base] = volume.volume_id

        return rtnval

    def apply_pods(self, *, spec: Any, client: Any,
                   volume_ids: Dict[str, str],
                   existing_pods: Dict[str, Any],
                   authkeys: Optional[Dict[str, str]] = None) -> List[ProvisionedResource]:
        """
            Launch a RunPod pod for every workload that is not already
            realised.

            :param spec: The :class:`RunpodWorkloadSpec`.
            :param client: The RunPod interop client.
            :param volume_ids: The neutral-name -> volume-id mapping returned
                by :meth:`ensure_network_volumes`.
            :param existing_pods: A name-keyed index of the live pods, used
                so an already-realised pod is skipped.
            :param authkeys: Optional ``workload-name -> Tailscale auth key``
                map for VPN-joined workloads.

            :returns: The list of :class:`ProvisionedResource` records the
                stage realised or re-confirmed.
        """
        effective_authkeys: Dict[str, str] = {}
        if authkeys is not None:
            effective_authkeys = authkeys

        run_short = spec.run_id_short
        cloud_type = self._cloud_type(spec=spec)

        rtnval: List[ProvisionedResource] = []
        all_workloads = list(spec.jobs) + list(spec.services)
        for workload in all_workloads:
            name = pod_name(workload_name=workload.name,
                            run_id_short=run_short)

            existing = existing_pods.get(name)
            if existing is not None:
                rtnval.append(self._resource_from_pod(pod=existing))
                continue

            vpn_join = spec.vpn_joins.get(workload.name)
            authkey = effective_authkeys.get(workload.name)
            start_script = self._renderer.render(workload=workload,
                                                 vpn_join=vpn_join,
                                                 authkey=authkey,
                                                 hostname=name)

            launch_spec = self._build_launch_spec(
                workload=workload, name=name, cloud_type=cloud_type,
                start_script=start_script, volume_ids=volume_ids)
            pod = client.launch_pod(spec=launch_spec)
            rtnval.append(self._resource_from_pod(pod=pod))

        return rtnval

    def _build_launch_spec(self, *, workload: Any, name: str,
                           cloud_type: RunpodCloudType,
                           start_script: str,
                           volume_ids: Dict[str, str]) -> RunpodPodLaunchSpec:
        """
            Build the :class:`RunpodPodLaunchSpec` for a workload.

            :param workload: The workload backing the pod.
            :param name: The composed pod name.
            :param cloud_type: The RunPod capacity-tier cloud type.
            :param start_script: The rendered container start script.
            :param volume_ids: The neutral-name -> volume-id mapping.

            :returns: A populated :class:`RunpodPodLaunchSpec`.
        """
        gpu_type_id = self._resolver.gpu_type_for_workload(workload=workload)
        if gpu_type_id is None:
            gpu_type_id = ""

        gpu_count = 1
        accelerators = getattr(workload, "accelerators", None)
        if accelerators is not None and len(accelerators) > 0:
            gpu_count = getattr(accelerators[0], "count", 1)

        mount_ids: List[str] = []
        mounts = getattr(workload, "shared_fs_mounts", None)
        if mounts is not None:
            for mount in mounts:
                fs_name = getattr(mount, "filesystem_name", None)
                volume_id = volume_ids.get(fs_name)
                if volume_id is not None:
                    mount_ids.append(volume_id)

        env = dict(getattr(workload, "env", {}) or {})

        rtnval = RunpodPodLaunchSpec(
            name=name, gpu_type_id=gpu_type_id, gpu_count=gpu_count,
            image_name=workload.image, volume_mounts=mount_ids,
            env=env, cloud_type=cloud_type,
            container_start_command=start_script)
        return rtnval

    def _cloud_type(self, *, spec: Any) -> RunpodCloudType:
        """
            Map the spec tier onto a :class:`RunpodCloudType`.

            :param spec: The :class:`RunpodWorkloadSpec`.

            :returns: The matching :class:`RunpodCloudType`.
        """
        if spec.tier == RUNPOD_TIER_COMMUNITY:
            rtnval = RunpodCloudType.COMMUNITY
            return rtnval

        rtnval = RunpodCloudType.SECURE
        return rtnval

    def _resource_from_pod(self, *, pod: Any) -> ProvisionedResource:
        """
            Adapt a RunPod pod record into a :class:`ProvisionedResource`.

            :param pod: The RunPod pod record.

            :returns: A populated :class:`ProvisionedResource`.
        """
        attributes: Dict[str, Any] = {
            "desired_status": getattr(pod, "desired_status", ""),
        }
        public_ip = getattr(pod, "public_ip", None)
        if public_ip is not None:
            attributes["public_ip"] = public_ip

        rtnval = ProvisionedResource(kind="Pod", name=pod.name,
                                     venue_id=pod.pod_id,
                                     attributes=attributes)
        return rtnval


__all__ = ["RpApplyStages"]
