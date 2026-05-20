# Design

## Overview

This spec adds the parallel `WorkloadVenue` hierarchy alongside `CloudVenue`.  Every
class shape mirrors the cloud side: a venue descriptor, an abstract provisioner with
the five-verb lifecycle, and a small set of declarative resource types (`WorkloadJob`,
`WorkloadCluster`, `WorkloadService`).

The §7 plan decisions drive three structural points:

1. `WorkloadVenueKind` is locked to four values forever; ECS/ACI/Cloud Run/Fargate are
   container-runtime conveniences and belong inside a `CloudVenue` (modelled later as
   `CloudContainerService`).  The enum is the contract.
2. Only Kubernetes implements `apply` in v1.  Slurm/Ray/Nomad subclasses *exist* and
   pass `validate` but raise `NotImplementedError` from `apply` — locking the public
   surface so future implementations are purely additive.
3. `WorkloadProvisioner` composes `CloudProvisioner` only when the workload venue is
   self-hosted on infrastructure the framework also provisions.  Venue-native
   platforms (CoreWeave, RunPod) leave the composition slot `None`.

---

## Architecture

```
                     ┌──────────────────────────────┐
                     │  Provisioning Engine Pipeline │
                     └──────────────┬───────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
        CloudVenue / CloudProvisioner    WorkloadVenue / WorkloadProvisioner
              (validate/plan/apply/                (validate/plan/apply/
               destroy/inventory)                   destroy/inventory)
                    │                               │
                    │       optional compose        │
                    └──────────────►◄──────────────┘
                            (self-hosted only)

   WorkloadVenueKind: KUBERNETES (v1) | SLURM | RAY | NOMAD (enum-only in v1)
   WorkloadResources: WorkloadJob | WorkloadCluster | WorkloadService
```

---

## Data Model

```python
class WorkloadVenueKind(Enum):
    KUBERNETES = "kubernetes"
    SLURM      = "slurm"
    RAY        = "ray"
    NOMAD      = "nomad"


class WorkloadVenue(SchemaObject):
    name: str
    kind: WorkloadVenueKind
    credential_ref: str
    endpoint: Optional[str]
    tags: List[Dict[str, str]]


class NodePoolSpec(SchemaObject):
    name: str
    count: int
    size: str
    accelerators: Optional[List[CloudAcceleratorSpec]]
    interconnect: Optional[CloudInterconnect]
    taints: List[Dict[str, str]]
    labels: Dict[str, str]


class AutoscalingSpec(SchemaObject):
    min_nodes: int
    max_nodes: int
    target_utilisation: float


class WorkloadCluster(SchemaObject):
    name: str
    node_pools: List[NodePoolSpec]
    accelerator_pools: List[NodePoolSpec]
    autoscaling: Optional[AutoscalingSpec]
    networking: Dict[str, Any]
    tags: List[Dict[str, str]]


class WorkloadJob(SchemaObject):
    name: str
    image: str
    command: List[str]
    resources: Dict[str, Any]                              # cpu, memory hints
    accelerators: Optional[List[CloudAcceleratorSpec]]
    replicas: int
    restart_policy: Literal["Never", "OnFailure"]
    env: Dict[str, str]
    shared_fs_mounts: Optional[List[SharedFsMountSpec]]
    network: Optional[str]


class WorkloadService(SchemaObject):
    name: str
    image: str
    command: List[str]
    resources: Dict[str, Any]
    accelerators: Optional[List[CloudAcceleratorSpec]]
    replicas: int
    ports: List[Dict[str, Any]]
    env: Dict[str, str]
    shared_fs_mounts: Optional[List[SharedFsMountSpec]]
    exposure: Literal["ClusterIP", "LoadBalancer", "NodePort"]
```

### Abstract Provisioner

```python
class WorkloadProvisioner(ABC):
    def __init__(self, *, venue: WorkloadVenue,
                 cloud_provisioner: Optional["CloudProvisioner"] = None) -> None: ...

    @abstractmethod
    def validate(self, *, aspects: Aspects) -> None: ...

    @abstractmethod
    def plan(self, *, aspects: Aspects) -> "ProvisioningPlan": ...

    @abstractmethod
    def apply(self, *, aspects: Aspects) -> "ProvisioningResult": ...

    @abstractmethod
    def destroy(self, *, aspects: Aspects) -> None: ...

    @abstractmethod
    def inventory(self, *, aspects: Aspects) -> List["ProvisionedResource"]: ...
```

The `ProvisioningPlan`, `ProvisioningResult`, and `ProvisionedResource` types are
shared with `CloudProvisioner` (see
[cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md)).

---

## V1 Implementations

| Subclass                       | Status                          |
| ------------------------------ | ------------------------------- |
| `KubernetesWorkloadProvisioner` | implemented (v1)                |
| `SlurmWorkloadProvisioner`      | declared; `apply` raises NIE    |
| `RayWorkloadProvisioner`        | declared; `apply` raises NIE    |
| `NomadWorkloadProvisioner`      | declared; `apply` raises NIE    |

`KubernetesWorkloadProvisioner` consumes `automojo-interop-kubernetes` for all API
calls.  CoreWeave's provisioner subclasses `KubernetesWorkloadProvisioner` and
overrides only the credential exchange (`CoreweaveApiCredential → kubeconfig`).

---

## Module Layout

```
source/packages/automojo/provisioning/model/workload/
├── workloadvenue.py
├── workloadvenuekind.py
├── workloadprovisioner.py             # abstract base
├── workloadjob.py
├── workloadcluster.py
├── workloadservice.py
├── nodepoolspec.py
└── autoscalingspec.py

source/packages/automojo/provisioning/venues/kubernetes/
└── kubernetesworkloadprovisioner.py

source/packages/automojo/provisioning/venues/slurm/
└── slurmworkloadprovisioner.py        # NIE in v1

source/packages/automojo/provisioning/venues/ray/
└── rayworkloadprovisioner.py          # NIE in v1

source/packages/automojo/provisioning/venues/nomad/
└── nomadworkloadprovisioner.py        # NIE in v1
```

---

## See Also

- [cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md) — shared
  plan/result/inventory dataclasses.
- [accelerator-and-interconnect-model](../accelerator-and-interconnect-model/design.md)
  — node-pool accelerator/interconnect fields.
- [accelerator-catalog](../accelerator-catalog/design.md) — accelerator resolution.
- [provisioning-engine-pipeline](../provisioning-engine-pipeline/design.md) — drives a
  mixed list of `CloudVenue` and `WorkloadVenue` entries.
- [workload-provisioning-config-schema](../../../automojo-configuration/specs/workload-provisioning-config-schema/design.md)
  — YAML schema fragment consumed by `from_dict`.

---

## Testing Strategy

- **Unit tests** — round-trip every class; reject invalid replicas, exposure
  mismatches, malformed enum values.
- **Subclass NIE tests** — assert `SlurmWorkloadProvisioner.apply` /
  `RayWorkloadProvisioner.apply` / `NomadWorkloadProvisioner.apply` raise
  `NotImplementedError` with a stable message format.
- **Composition tests** — when a `WorkloadProvisioner` is constructed with a
  `CloudProvisioner`, the engine drives the cloud apply first and destroys in
  reverse.
- **Validation tests** — node pool accelerators that the catalog says are unsupported
  on the venue raise `SchemaSemanticError`.
- No property tests required at this layer; the heavy invariants live in the
  accelerator catalog and lifecycle specs.
