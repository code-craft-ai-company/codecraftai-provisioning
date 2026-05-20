# Requirements

## Introduction

`WorkloadVenue` is the sibling concept to `CloudVenue`.  Where `CloudVenue` represents
a venue that hands out **VMs**, `WorkloadVenue` represents a venue whose unit of
provisioning is a **scheduler-managed workload** — Kubernetes Jobs/Deployments,
Slurm batch jobs, Ray clusters, Nomad allocations.  CoreWeave and RunPod are the v1
motivating cases; self-hosted Slurm and Ray follow the same shape.

Per the §7.6 plan decision the scope is narrow: `WorkloadVenue.kind ∈ {KUBERNETES,
SLURM, RAY, NOMAD}`.  ECS, ACI, Cloud Run, Fargate, etc. are explicitly NOT
WorkloadVenues — they are container conveniences inside a `CloudVenue`.  The enum
ships complete on day one, but only `KUBERNETES` is implemented in v1; the others
raise `NotImplementedError` from `apply` so adding them later is purely additive.

This spec defines five classes (`WorkloadVenue`, `WorkloadProvisioner`, `WorkloadJob`,
`WorkloadCluster`, `WorkloadService`) plus the `WorkloadVenueKind` enum, and pins them
to the same `validate / plan / apply / destroy / inventory` lifecycle every
provisioner uses.

---

## Requirements

### Requirement 1: WorkloadVenueKind Enum

**User Story:** As a framework author, I want the workload venue kind locked to a
small enum that won't grow accidentally.

#### Acceptance Criteria

1. THE SYSTEM SHALL define `WorkloadVenueKind` with exactly the values
   `KUBERNETES`, `SLURM`, `RAY`, `NOMAD`.
2. THE SYSTEM SHALL reject construction with any other value at class construction
   time via `SchemaValidationError`.
3. THE SYSTEM SHALL document that v1 implements only `KUBERNETES`; the other three
   values are reserved-but-not-implemented (per §7.6 decision).

---

### Requirement 2: WorkloadVenue Data Class

**User Story:** As a provisioning author, I want to describe a workload venue.

#### Acceptance Criteria

1. THE SYSTEM SHALL expose `WorkloadVenue(name, kind: WorkloadVenueKind,
   credential_ref: str, endpoint: Optional[str], tags)` as a `SchemaObject`.
2. WHEN `credential_ref` does not resolve to a registered credential of an expected
   type for the `kind` THE SYSTEM SHALL raise `SchemaSemanticError` during validate.
3. WHERE `kind == KUBERNETES` THE SYSTEM SHALL accept either a `KubeconfigCredential`
   or a venue-specific credential that exchanges for a kubeconfig (e.g.
   `CoreweaveApiCredential`).

---

### Requirement 3: WorkloadProvisioner Abstract Base

**User Story:** As a framework author, I want every workload-venue plugin to honour
the same five-verb lifecycle.

#### Acceptance Criteria

1. THE SYSTEM SHALL expose `WorkloadProvisioner` as an abstract base with the same
   shape as `CloudProvisioner`: `validate`, `plan`, `apply`, `destroy`, `inventory`.
2. THE SYSTEM SHALL require every method to accept an `aspects` named parameter.
3. WHEN a subclass with `WorkloadVenueKind.SLURM`, `RAY`, or `NOMAD` has its `apply`
   invoked THE SYSTEM SHALL raise `NotImplementedError` with a pointer to the
   tracking issue (per §7.6 decision; v1 ships enum only).

---

### Requirement 4: WorkloadJob

**User Story:** As a provisioning author, I want to declare a one-shot or batch
workload that the venue's scheduler will run.

#### Acceptance Criteria

1. THE SYSTEM SHALL expose `WorkloadJob(name, image: str, command: List[str],
   resources: Dict[str, Any], accelerators: Optional[List[CloudAcceleratorSpec]],
   replicas: int, restart_policy: Literal["Never", "OnFailure"], env: Dict[str, str],
   shared_fs_mounts: Optional[List[SharedFsMountSpec]], network: Optional[str])`.
2. WHEN `replicas <= 0` THE SYSTEM SHALL raise `SchemaValidationError`.
3. WHEN any `accelerators[*].model` does not resolve on the parent venue THE SYSTEM
   SHALL raise `SchemaSemanticError` during validate.

---

### Requirement 5: WorkloadCluster

**User Story:** As a provisioning author for long-lived training, I want to declare
a cluster with node pools that have different shapes.

#### Acceptance Criteria

1. THE SYSTEM SHALL expose `WorkloadCluster(name, node_pools: List[NodePoolSpec],
   accelerator_pools: List[NodePoolSpec], autoscaling: Optional[AutoscalingSpec],
   networking: Dict[str, Any], tags)`.
2. THE SYSTEM SHALL expose `NodePoolSpec(name, count: int, size: str,
   accelerators: Optional[List[CloudAcceleratorSpec]],
   interconnect: Optional[CloudInterconnect], taints, labels)`.
3. WHEN any node pool's `accelerators` references a neutral name unsupported on the
   parent venue THE SYSTEM SHALL raise `SchemaSemanticError` during validate.

---

### Requirement 6: WorkloadService

**User Story:** As a provisioning author for inference or platform services, I want
to declare long-running services (Deployments / StatefulSets) that the workload
venue will keep alive.

#### Acceptance Criteria

1. THE SYSTEM SHALL expose `WorkloadService(name, image, command, resources,
   accelerators, replicas, ports: List[Dict[str, Any]], env, shared_fs_mounts,
   exposure: Literal["ClusterIP", "LoadBalancer", "NodePort"])`.
2. WHEN `exposure == "LoadBalancer"` and the parent venue does not support managed
   load balancers THE SYSTEM SHALL raise `SchemaSemanticError`.

---

### Requirement 7: Composition with CloudProvisioner

**User Story:** As a framework author, I want a workload venue to optionally compose
a cloud venue underneath it (self-hosted K8s on AWS, for example).

#### Acceptance Criteria

1. THE SYSTEM SHALL allow a `WorkloadProvisioner` constructor to accept an optional
   `cloud_provisioner: Optional[CloudProvisioner]` parameter.
2. WHEN composition is used THE SYSTEM SHALL drive the cloud provisioner's
   `apply` before the workload provisioner's `apply` (and reverse on destroy).
3. WHERE the workload venue is venue-native (CoreWeave, RunPod) THE SYSTEM SHALL
   leave `cloud_provisioner` as `None`.
