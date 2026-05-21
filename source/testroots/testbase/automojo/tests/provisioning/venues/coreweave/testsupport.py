"""
    .. module:: testsupport
        :platform: Darwin, Linux, Unix, Windows
        :synopsis: Mock CoreweaveClient / KubernetesClient and fixture
                   builders for the CoreWeave workload-provisioner tests.

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

from automojo.provisioning.venues.coreweave.coreweaveworkloadspec import (
    CoreweaveWorkloadSpec
)
from automojo.provisioning.venues.coreweave.coreweaveworkloadprovisioner import (
    CoreweaveWorkloadProvisioner
)


# ----------------------------------------------------------------------
# Fake CoreWeave node-pool record
# ----------------------------------------------------------------------

class FakeNodePool:
    """
        A minimal stand-in for :class:`CoreweaveNodePool`.
    """

    def __init__(self, *, name: str, gpu_model: str,
                 interconnect: str = "ETHERNET") -> None:
        """
            Initialise the fake node pool.

            :param name: The pool name.
            :param gpu_model: The GPU model offered.
            :param interconnect: The interconnect topology.

            :returns: ``None``.
        """
        self.id = name
        self.cluster_id = "cluster-1"
        self.name = name
        self.gpu_model = gpu_model
        self.gpus_per_node = 8
        self.node_count = 4
        self.interconnect = interconnect
        return


# ----------------------------------------------------------------------
# Fake kubeconfig
# ----------------------------------------------------------------------

class FakeKubeconfig:
    """
        A minimal stand-in for :class:`CoreweaveKubeconfig`.
    """

    def __init__(self) -> None:
        """
            Initialise the fake kubeconfig.

            :returns: ``None``.
        """
        self.cluster_id = "cluster-1"
        self.api_endpoint = "https://k8s.test:6443"
        return

    def as_dict(self) -> Dict[str, Any]:
        """
            Return a parsed kubeconfig dict.

            :returns: A minimal kubeconfig dict.
        """
        rtnval = {"apiVersion": "v1", "kind": "Config"}
        return rtnval


# ----------------------------------------------------------------------
# Mock CoreweaveClient
# ----------------------------------------------------------------------

class _MockNodePoolsGroup:
    """
        Mock ``node_pools`` api group.
    """

    def __init__(self, *, pools: List[FakeNodePool]) -> None:
        """
            Initialise the mock group.

            :param pools: The node pools to serve.

            :returns: ``None``.
        """
        self._pools = pools
        return

    def list(self, *, cluster_id: str,
             aspects: Any = None) -> List[FakeNodePool]:
        """
            Return the configured node pools.

            :param cluster_id: The cluster identifier (ignored).
            :param aspects: Behaviour control (ignored).

            :returns: The configured node pool list.
        """
        rtnval = self._pools
        return rtnval


class MockCoreweaveClient:
    """
        Deterministic stand-in for :class:`CoreweaveClient`.
    """

    def __init__(self, *, pools: Optional[List[FakeNodePool]] = None) -> None:
        """
            Initialise the mock client.

            :param pools: The node pools to serve. Defaults to a single
                H100 pool.

            :returns: ``None``.
        """
        if pools is None:
            pools = [FakeNodePool(name="h100-pool", gpu_model="H100_SXM",
                                  interconnect="INFINIBAND_NDR")]
        self.node_pools = _MockNodePoolsGroup(pools=pools)
        self.mint_count = 0
        self.credential = "fake-credential"
        return

    def mint_kubeconfig(self, *, cluster_id: str,
                        aspects: Any = None) -> FakeKubeconfig:
        """
            Mint a fake kubeconfig.

            :param cluster_id: The cluster identifier (ignored).
            :param aspects: Behaviour control (ignored).

            :returns: A :class:`FakeKubeconfig`.
        """
        self.mint_count = self.mint_count + 1
        rtnval = FakeKubeconfig()
        return rtnval


# ----------------------------------------------------------------------
# Mock KubernetesClient
# ----------------------------------------------------------------------

class _RecordInfo:
    """
        A minimal info DTO returned by the mock primitives.
    """

    def __init__(self, *, name: str, namespace: str = "default",
                 phase: str = "Running",
                 labels: Optional[Dict[str, str]] = None) -> None:
        """
            Initialise the record.

            :param name: The resource name.
            :param namespace: The resource namespace.
            :param phase: The resource phase.
            :param labels: The resource labels.

            :returns: ``None``.
        """
        self.name = name
        self.namespace = namespace
        self.phase = phase
        self.labels = labels if labels is not None else {}
        self.cluster_ip = "10.0.0.1"
        return


class _MockPrimitive:
    """
        A mock workload primitive backed by an in-memory store.
    """

    def __init__(self, *, kind: str, store: Dict[str, _RecordInfo]) -> None:
        """
            Initialise the mock primitive.

            :param kind: The Kubernetes kind.
            :param store: The shared in-memory resource store.

            :returns: ``None``.
        """
        self._kind = kind
        self._store = store
        return

    def _key(self, *, name: str) -> str:
        """
            Compose the store key for a resource.

            :param name: The resource name.

            :returns: The store key.
        """
        rtnval = "{}/{}".format(self._kind, name)
        return rtnval

    def apply(self, *, spec: Any, namespace: str = "default",
              aspects: Any = None) -> _RecordInfo:
        """
            Create-or-update the resource (idempotent).

            :param spec: The typed Kubernetes spec.
            :param namespace: The target namespace.
            :param aspects: Behaviour control (ignored).

            :returns: A :class:`_RecordInfo`.
        """
        labels = getattr(spec, "labels", {})
        record = _RecordInfo(name=spec.name, namespace=namespace,
                             labels=dict(labels))
        self._store[self._key(name=spec.name)] = record
        return record

    def get(self, *, name: str, namespace: str = "default",
            aspects: Any = None) -> _RecordInfo:
        """
            Read the resource, raising when absent.

            :param name: The resource name.
            :param namespace: The target namespace.
            :param aspects: Behaviour control (ignored).

            :returns: A :class:`_RecordInfo`.

            :raises: ``KeyError`` when the resource is absent.
        """
        rtnval = self._store[self._key(name=name)]
        return rtnval

    def delete(self, *, name: str, namespace: str = "default",
               aspects: Any = None) -> None:
        """
            Delete the resource (idempotent).

            :param name: The resource name.
            :param namespace: The target namespace.
            :param aspects: Behaviour control (ignored).

            :returns: ``None``.
        """
        self._store.pop(self._key(name=name), None)
        return

    def list(self, *, namespace: str = "default",
             label_selector: Optional[str] = None,
             aspects: Any = None) -> List[_RecordInfo]:
        """
            List the resources, optionally filtered by a label selector.

            :param namespace: The target namespace.
            :param label_selector: A ``key=value`` selector, or ``None``.
            :param aspects: Behaviour control (ignored).

            :returns: A list of :class:`_RecordInfo`.
        """
        prefix = "{}/".format(self._kind)
        results: List[_RecordInfo] = []
        for key, record in self._store.items():
            if not key.startswith(prefix):
                continue
            if label_selector is not None and len(label_selector) > 0:
                sel_key, _, sel_value = label_selector.partition("=")
                if record.labels.get(sel_key, None) != sel_value:
                    continue
            results.append(record)
        return results


class _MockNamespacePrimitive(_MockPrimitive):
    """
        A mock namespace primitive (no namespace argument).
    """

    def apply(self, *, spec: Any, aspects: Any = None) -> _RecordInfo:
        """
            Create-or-update the namespace.

            :param spec: The typed namespace spec.
            :param aspects: Behaviour control (ignored).

            :returns: A :class:`_RecordInfo`.
        """
        labels = getattr(spec, "labels", {})
        record = _RecordInfo(name=spec.name, labels=dict(labels))
        self._store[self._key(name=spec.name)] = record
        return record

    def get(self, *, name: str, aspects: Any = None) -> _RecordInfo:
        """
            Read the namespace.

            :param name: The namespace name.
            :param aspects: Behaviour control (ignored).

            :returns: A :class:`_RecordInfo`.
        """
        rtnval = self._store[self._key(name=name)]
        return rtnval

    def delete(self, *, name: str, aspects: Any = None) -> None:
        """
            Delete the namespace.

            :param name: The namespace name.
            :param aspects: Behaviour control (ignored).

            :returns: ``None``.
        """
        self._store.pop(self._key(name=name), None)
        return


class MockKubernetesClient:
    """
        Deterministic stand-in for :class:`KubernetesClient`.
    """

    def __init__(self) -> None:
        """
            Initialise the mock client with empty in-memory stores.

            :returns: ``None``.
        """
        self._store: Dict[str, _RecordInfo] = {}
        self.jobs = _MockPrimitive(kind="Job", store=self._store)
        self.deployments = _MockPrimitive(kind="Deployment",
                                          store=self._store)
        self.statefulsets = _MockPrimitive(kind="StatefulSet",
                                           store=self._store)
        self.services = _MockPrimitive(kind="Service", store=self._store)
        self.pvcs = _MockPrimitive(kind="Pvc", store=self._store)
        self.namespaces = _MockNamespacePrimitive(kind="Namespace",
                                                  store=self._store)
        return


class MockVpnControlPlane:
    """
        A minimal mock of the ``IVPNControlPlane`` surface — auth-key
        minting and device de-registration.
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
        Build a Kubernetes :class:`WorkloadVenue` for tests.

        :returns: A :class:`WorkloadVenue`.
    """
    rtnval = WorkloadVenue(name="cw-venue", kind="kubernetes",
                           credential_ref="coreweave-token")
    return rtnval


def make_slurm_venue() -> WorkloadVenue:
    """
        Build a Slurm :class:`WorkloadVenue` for tests.

        :returns: A :class:`WorkloadVenue` with ``kind="slurm"``.
    """
    rtnval = WorkloadVenue(name="cw-slurm", kind="slurm",
                           credential_ref="coreweave-token")
    return rtnval


def make_gpu_job(*, name: str = "trainer") -> WorkloadJob:
    """
        Build a GPU-bearing :class:`WorkloadJob`.

        :param name: The job name.

        :returns: A :class:`WorkloadJob`.
    """
    accel = CloudAcceleratorSpec(kind="GPU", model="H100_SXM", count=8,
                                 memory_gb=80)
    rtnval = WorkloadJob(name=name, image="trainer:latest",
                         command=["python", "train.py"],
                         accelerators=[accel])
    return rtnval


def make_service(*, name: str = "inference") -> WorkloadService:
    """
        Build a :class:`WorkloadService`.

        :param name: The service name.

        :returns: A :class:`WorkloadService`.
    """
    rtnval = WorkloadService(name=name, image="server:latest",
                             ports=[{"port": 8080}])
    return rtnval


def make_spec(*, jobs=None, services=None,
              sub_mode: Optional[str] = None,
              vpn_joins: Optional[dict] = None) -> CoreweaveWorkloadSpec:
    """
        Build a :class:`CoreweaveWorkloadSpec`.

        :param jobs: Optional job list.
        :param services: Optional service list.
        :param sub_mode: Optional sub-mode flag.
        :param vpn_joins: Optional ``workload-name -> VPNJoinSpec`` map.

        :returns: A :class:`CoreweaveWorkloadSpec`.
    """
    rtnval = CoreweaveWorkloadSpec(run_id="run-0001", cluster_id="cluster-1",
                                   namespace="default", jobs=jobs,
                                   services=services, sub_mode=sub_mode,
                                   vpn_joins=vpn_joins)
    return rtnval


def make_provisioner(*, spec: Optional[CoreweaveWorkloadSpec] = None,
                     venue: Optional[WorkloadVenue] = None,
                     coreweave_client: Optional[MockCoreweaveClient] = None,
                     kubernetes_client: Optional[MockKubernetesClient] = None,
                     vpn_control_plane: Optional[Any] = None) -> CoreweaveWorkloadProvisioner:
    """
        Build a :class:`CoreweaveWorkloadProvisioner` wired to mock clients.

        :param spec: Optional spec bundle.
        :param venue: Optional workload venue.
        :param coreweave_client: Optional mock CoreWeave client.
        :param kubernetes_client: Optional mock Kubernetes client.
        :param vpn_control_plane: Optional mock VPN control plane.

        :returns: A :class:`CoreweaveWorkloadProvisioner`.
    """
    if spec is None:
        spec = make_spec(jobs=[make_gpu_job()])
    if venue is None:
        venue = make_venue()
    if coreweave_client is None:
        coreweave_client = MockCoreweaveClient()
    if kubernetes_client is None:
        kubernetes_client = MockKubernetesClient()

    rtnval = CoreweaveWorkloadProvisioner(
        venue=venue, coreweave_client=coreweave_client, spec=spec,
        kubernetes_client=kubernetes_client,
        vpn_control_plane=vpn_control_plane)
    return rtnval
