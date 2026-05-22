"""
    .. module:: testsupport
        :platform: Darwin, Linux, Unix, Windows
        :synopsis: Mock RunPod interop client and fixture builders for the
                   RunPod workload-provisioner tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.provisioning.model.cloud.cloudacceleratorspec import (
    CloudAcceleratorSpec
)
from automojo.provisioning.model.workload.workloadjob import WorkloadJob
from automojo.provisioning.model.workload.workloadservice import WorkloadService
from automojo.provisioning.model.workload.workloadvenue import WorkloadVenue

from automojo.provisioning.venues.runpod.runpodworkloadprovisioner import (
    RunpodWorkloadProvisioner
)
from automojo.provisioning.venues.runpod.runpodworkloadspec import (
    RunpodWorkloadSpec
)


TEST_RUN_ID = "abcd1234efgh5678"
TEST_DATA_CENTER = "US-CA-1"


# ----------------------------------------------------------------------
# Fake interop model records
# ----------------------------------------------------------------------

class FakeGpuType:
    """
        A minimal stand-in for the interop ``RunpodGpuType`` record.
    """

    def __init__(self, *, gpu_type_id: str,
                 secure_data_centers: Optional[List[str]] = None,
                 community_data_centers: Optional[List[str]] = None) -> None:
        """
            Initialise the fake GPU type.

            :param gpu_type_id: The RunPod GPU type identifier.
            :param secure_data_centers: Secure Cloud data centers.
            :param community_data_centers: Community Cloud data centers.

            :returns: ``None``.
        """
        self.gpu_type_id = gpu_type_id
        self.secure_data_centers = secure_data_centers or []
        self.community_data_centers = community_data_centers or []
        return


class FakePod:
    """
        A minimal stand-in for the interop ``RunpodPod`` record.
    """

    def __init__(self, *, pod_id: str, name: str,
                 gpu_type_id: str = "NVIDIA H100 80GB HBM3",
                 desired_status: str = "RUNNING",
                 public_ip: Optional[str] = None) -> None:
        """
            Initialise the fake pod.

            :param pod_id: The pod identifier.
            :param name: The pod name.
            :param gpu_type_id: The pod GPU type.
            :param desired_status: The pod desired status.
            :param public_ip: The pod public IP.

            :returns: ``None``.
        """
        self.pod_id = pod_id
        self.name = name
        self.gpu_type_id = gpu_type_id
        self.desired_status = desired_status
        self.public_ip = public_ip
        return


class FakeVolume:
    """
        A minimal stand-in for the interop ``RunpodNetworkVolume`` record.
    """

    def __init__(self, *, volume_id: str, name: str, size_gb: int = 50,
                 data_center_id: str = TEST_DATA_CENTER) -> None:
        """
            Initialise the fake volume.

            :param volume_id: The volume identifier.
            :param name: The volume name.
            :param size_gb: The volume size in GiB.
            :param data_center_id: The volume data center.

            :returns: ``None``.
        """
        self.volume_id = volume_id
        self.name = name
        self.size_gb = size_gb
        self.data_center_id = data_center_id
        return


# ----------------------------------------------------------------------
# Mock RunPod interop client
# ----------------------------------------------------------------------

class MockRunpodClient:
    """
        A deterministic, in-memory mock of the RunPod interop client surface
        the venue provisioner consumes.
    """

    def __init__(self, *, gpu_types: Optional[List[FakeGpuType]] = None,
                 pods: Optional[List[FakePod]] = None,
                 volumes: Optional[List[FakeVolume]] = None) -> None:
        """
            Initialise the mock client.

            :param gpu_types: The GPU-type catalog the mock exposes.
            :param pods: The pods the mock starts with.
            :param volumes: The volumes the mock starts with.

            :returns: ``None``.
        """
        if gpu_types is None:
            gpu_types = [FakeGpuType(gpu_type_id="NVIDIA H100 80GB HBM3",
                                     secure_data_centers=[TEST_DATA_CENTER],
                                     community_data_centers=["EU-1"])]
        self._gpu_types = gpu_types
        self._pods: List[FakePod] = list(pods) if pods is not None else []
        self._volumes: List[FakeVolume] = list(volumes) if volumes is not None else []
        self._launch_count = 0
        self._terminate_count = 0
        self._volume_create_count = 0
        self._next_pod_index = 0
        self._next_volume_index = 0
        return

    @property
    def launch_count(self) -> int:
        """
            The number of pod launches the mock has served.

            :returns: The launch count.
        """
        return self._launch_count

    @property
    def terminate_count(self) -> int:
        """
            The number of pod terminations the mock has served.

            :returns: The terminate count.
        """
        return self._terminate_count

    @property
    def volume_create_count(self) -> int:
        """
            The number of volume creations the mock has served.

            :returns: The volume create count.
        """
        return self._volume_create_count

    def list_gpu_types(self, *, aspects: Any = None) -> List[FakeGpuType]:
        """
            Return the GPU-type catalog.

            :param aspects: Ignored behaviour control.

            :returns: The GPU-type list.
        """
        return list(self._gpu_types)

    def list_pods(self, *, aspects: Any = None) -> List[FakePod]:
        """
            Return the live pods.

            :param aspects: Ignored behaviour control.

            :returns: The pod list.
        """
        return list(self._pods)

    def list_network_volumes(self, *, aspects: Any = None) -> List[FakeVolume]:
        """
            Return the live volumes.

            :param aspects: Ignored behaviour control.

            :returns: The volume list.
        """
        return list(self._volumes)

    def create_network_volume(self, *, spec: Any,
                              aspects: Any = None) -> FakeVolume:
        """
            Create a volume idempotently on name + data center.

            :param spec: The interop network-volume spec.
            :param aspects: Ignored behaviour control.

            :returns: The created or existing :class:`FakeVolume`.
        """
        for volume in self._volumes:
            if volume.name == spec.name:
                if volume.data_center_id == spec.data_center_id:
                    return volume

        self._volume_create_count = self._volume_create_count + 1
        self._next_volume_index = self._next_volume_index + 1
        volume = FakeVolume(volume_id="vol-{}".format(self._next_volume_index),
                            name=spec.name, size_gb=spec.size_gb,
                            data_center_id=spec.data_center_id)
        self._volumes.append(volume)
        return volume

    def delete_network_volume(self, *, volume_id: str,
                              aspects: Any = None) -> None:
        """
            Delete a volume by id (no-op on an unknown id).

            :param volume_id: The volume identifier.
            :param aspects: Ignored behaviour control.

            :returns: ``None``.
        """
        self._volumes = [v for v in self._volumes
                         if v.volume_id != volume_id]
        return

    def launch_pod(self, *, spec: Any, aspects: Any = None) -> FakePod:
        """
            Launch a pod from an interop launch spec.

            :param spec: The interop pod launch spec.
            :param aspects: Ignored behaviour control.

            :returns: The launched :class:`FakePod`.
        """
        self._launch_count = self._launch_count + 1
        self._next_pod_index = self._next_pod_index + 1
        pod = FakePod(pod_id="pod-{}".format(self._next_pod_index),
                      name=spec.name, gpu_type_id=spec.gpu_type_id,
                      desired_status="RUNNING", public_ip="203.0.113.1")
        self._pods.append(pod)
        return pod

    def stop_pod(self, *, pod_id: str, aspects: Any = None) -> Optional[FakePod]:
        """
            Stop a pod by id.

            :param pod_id: The pod identifier.
            :param aspects: Ignored behaviour control.

            :returns: The stopped pod, or ``None`` when unknown.
        """
        for pod in self._pods:
            if pod.pod_id == pod_id:
                pod.desired_status = "EXITED"
                return pod
        return None

    def terminate_pod(self, *, pod_id: str, aspects: Any = None) -> None:
        """
            Terminate a pod by id (no-op on an unknown id).

            :param pod_id: The pod identifier.
            :param aspects: Ignored behaviour control.

            :returns: ``None``.
        """
        self._terminate_count = self._terminate_count + 1
        self._pods = [p for p in self._pods if p.pod_id != pod_id]
        return


# ----------------------------------------------------------------------
# Mock VPN control plane
# ----------------------------------------------------------------------

class MockVpnControlPlane:
    """
        A minimal mock of the ``IVPNControlPlane`` surface the provisioner
        consumes — auth-key minting and device de-registration.
    """

    def __init__(self) -> None:
        """
            Initialise the mock VPN control plane.

            :returns: ``None``.
        """
        self.deleted_devices: List[str] = []
        self._mint_count = 0
        return

    def mint_authkey(self, *, reusable: bool, ephemeral: bool,
                     tags: List[str], ttl_seconds: int,
                     aspects: Any = None) -> str:
        """
            Mint a deterministic fake auth key.

            :param reusable: Whether the key is reusable.
            :param ephemeral: Whether the registration is ephemeral.
            :param tags: The tags bound to the key.
            :param ttl_seconds: The key TTL.
            :param aspects: Ignored behaviour control.

            :returns: A fake auth-key string.
        """
        self._mint_count = self._mint_count + 1
        rtnval = "tskey-fake-{}".format(self._mint_count)
        return rtnval

    def delete_device(self, *, device_id: str, aspects: Any = None) -> None:
        """
            Record a device de-registration.

            :param device_id: The device identifier.
            :param aspects: Ignored behaviour control.

            :returns: ``None``.
        """
        self.deleted_devices.append(device_id)
        return


# ----------------------------------------------------------------------
# Fixture builders
# ----------------------------------------------------------------------

def make_venue() -> WorkloadVenue:
    """
        Build a :class:`WorkloadVenue` for the RunPod tests.

        :returns: A populated :class:`WorkloadVenue`.
    """
    rtnval = WorkloadVenue(name="runpod-venue", kind="container",
                           credential_ref="runpod-key")
    return rtnval


def make_gpu_job(*, name: str = "trainer") -> WorkloadJob:
    """
        Build an H100 GPU :class:`WorkloadJob`.

        :param name: The job name.

        :returns: A populated :class:`WorkloadJob`.
    """
    accelerator = CloudAcceleratorSpec(kind="GPU", model="H100_SXM",
                                       count=1, memory_gb=80)
    rtnval = WorkloadJob(name=name, image="trainer:1.0",
                         command=["python", "train.py"],
                         accelerators=[accelerator])
    return rtnval


def make_service(*, name: str = "infer") -> WorkloadService:
    """
        Build an H100 GPU :class:`WorkloadService`.

        :param name: The service name.

        :returns: A populated :class:`WorkloadService`.
    """
    accelerator = CloudAcceleratorSpec(kind="GPU", model="H100_SXM",
                                       count=1, memory_gb=80)
    rtnval = WorkloadService(name=name, image="infer:1.0",
                             accelerators=[accelerator])
    return rtnval


def make_spec(*, jobs: Optional[List[Any]] = None,
              services: Optional[List[Any]] = None,
              tier: Optional[str] = None,
              network_volumes: Optional[List[Dict[str, Any]]] = None,
              vpn_joins: Optional[Dict[str, Any]] = None,
              buckets: Optional[List[Any]] = None,
              load_balancers: Optional[List[Any]] = None,
              dns_records: Optional[List[Any]] = None,
              interconnects: Optional[List[Any]] = None,
              networks: Optional[List[Any]] = None,
              tags: Optional[List[Dict[str, str]]] = None) -> RunpodWorkloadSpec:
    """
        Build a :class:`RunpodWorkloadSpec` for the RunPod tests.

        :param jobs: The workload jobs.
        :param services: The workload services.
        :param tier: The capacity tier.
        :param network_volumes: The network-volume requests.
        :param vpn_joins: The per-workload VPN joins.
        :param buckets: The object-bucket requests.
        :param load_balancers: The load-balancer requests.
        :param dns_records: The DNS-record requests.
        :param interconnects: The interconnect requests.
        :param networks: The network requests.
        :param tags: The neutral tag list.

        :returns: A populated :class:`RunpodWorkloadSpec`.
    """
    rtnval = RunpodWorkloadSpec(
        run_id=TEST_RUN_ID, data_center_id=TEST_DATA_CENTER, tier=tier,
        jobs=jobs, services=services, network_volumes=network_volumes,
        vpn_joins=vpn_joins, buckets=buckets, load_balancers=load_balancers,
        dns_records=dns_records, interconnects=interconnects,
        networks=networks, tags=tags)
    return rtnval


def make_provisioner(*, spec: RunpodWorkloadSpec,
                     runpod_client: Optional[MockRunpodClient] = None,
                     venue: Optional[WorkloadVenue] = None,
                     vpn_control_plane: Optional[Any] = None) -> RunpodWorkloadProvisioner:
    """
        Build a :class:`RunpodWorkloadProvisioner` for the RunPod tests.

        :param spec: The :class:`RunpodWorkloadSpec`.
        :param runpod_client: Optional mock client.
        :param venue: Optional :class:`WorkloadVenue`.
        :param vpn_control_plane: Optional mock VPN control plane.

        :returns: A constructed :class:`RunpodWorkloadProvisioner`.
    """
    effective_client = runpod_client
    if effective_client is None:
        effective_client = MockRunpodClient()

    effective_venue = venue
    if effective_venue is None:
        effective_venue = make_venue()

    rtnval = RunpodWorkloadProvisioner(venue=effective_venue,
                                       runpod_client=effective_client,
                                       spec=spec,
                                       vpn_control_plane=vpn_control_plane)
    return rtnval
