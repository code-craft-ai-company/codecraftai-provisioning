# Requirements — CoreWeave Workload Provisioner

## Introduction

The `venue-coreweave` feature provides `codecraftai-provisioning` with the ability
to stand up GPU workloads on CoreWeave Cloud (CKS — CoreWeave Kubernetes
Service).  It implements the **`WorkloadProvisioner`** lifecycle per PLAN
§7.2: `validate / plan / apply / destroy / inventory` on `WorkloadCluster`,
`WorkloadJob`, and `WorkloadService` rather than on `CloudInstance`.  It
composes `codecraftai-interop-kubernetes` (the official Python K8s client wrapped
in Aspects per IMPLEMENTATION-PLAN §1.17) to talk to the cluster, and
`codecraftai-interop-coreweave` to mint a kubeconfig and to interrogate
CoreWeave-specific machine types and node pools.

Per PLAN §7.6: CoreWeave auth flow is "mint kubeconfig, then drive Kubernetes."
The CoreWeave provisioner itself only knows about kubeconfig acquisition,
node-pool selection, the optional Sunk Slurm-on-K8s mode, and CoreWeave's
shared-FS bindings (typically VAST or WEKA via CSI).  Everything else
(Deployments, Jobs, StatefulSets, PVCs, Services, Ingresses) is delegated to
the K8s interop.

Every method on `CoreweaveWorkloadProvisioner` accepts `aspects: Aspects`.

---

## Requirements

### Requirement 1: Validate a Spec

#### Acceptance Criteria

1. WHEN `validate(spec, aspects)` is called THE SYSTEM SHALL ensure every
   `WorkloadJob`/`WorkloadService` resolves to a CoreWeave node pool with the
   requested accelerator.
2. WHEN the spec contains `WorkloadVenue.kind in {SLURM, RAY, NOMAD}` and
   `sub_mode != "sunk"` THE SYSTEM SHALL fail with the "v1 ships
   enumerants, only K8s + Sunk implemented" message from §7.6.
3. WHEN the spec contains `CloudSharedFilesystem(kind=LUSTRE|WEKA|VAST,
   existing_id=...)` THE SYSTEM SHALL look up the CSI binding; missing
   `existing_id` fails (provision path not in v1).
4. WHEN no kubeconfig source is configured THE SYSTEM SHALL fail with a
   credential error pointing at `CoreweaveApiCredential`.

---

### Requirement 2: Plan

#### Acceptance Criteria

1. WHEN `plan(spec, aspects)` is called THE SYSTEM SHALL ensure a fresh
   kubeconfig (TTL-managed via `CoreweaveClient.mint_kubeconfig`) and then
   diff every K8s resource via the K8s interop's `get_*` calls.
2. WHEN a Deployment / Job / Service / Ingress / PVC drifts THE SYSTEM SHALL
   emit `UPDATE`.
3. WHEN re-applying an already-applied spec THE SYSTEM SHALL emit only SKIP
   actions.

---

### Requirement 3: Apply Idempotently

#### Acceptance Criteria

1. WHEN `apply(spec, aspects)` is called THE SYSTEM SHALL execute namespace
   ensure → ServiceAccount/RoleBinding → Secret (for VPN auth keys, image
   pull) → PVC (shared-FS bindings) → Deployment/StatefulSet → Service →
   Ingress.
2. WHEN `sub_mode="sunk"` is configured for a Slurm workload THE SYSTEM SHALL
   render the Sunk Slurm-on-K8s manifest set and apply it via the K8s
   interop.
3. WHEN a workload carries `vpn_join` THE SYSTEM SHALL render the cloud-init
   snippet from [vpn-join-spec](../vpn-join-spec/design.md) and inject it
   either as a `tailscale up` container sidecar in each Pod template or as a
   subnet-router DaemonSet, per the workload's connectivity profile.
4. WHEN any DELETE is planned and `aspects.confirm` is false THE SYSTEM SHALL
   raise `ConfirmationRequiredError`.

---

### Requirement 4: Destroy

#### Acceptance Criteria

1. WHEN `destroy(spec, aspects)` is called with confirm THE SYSTEM SHALL
   delete K8s resources in reverse dependency order: Ingress → Service →
   Deployment/StatefulSet → PVC → Secret → ServiceAccount → Namespace (only
   if owned by the run-id).
2. WHEN a VPN sidecar/DaemonSet was deployed THE SYSTEM SHALL invoke
   `IVPNControlPlane.delete_device` for each registered device.

---

### Requirement 5: Inventory

#### Acceptance Criteria

1. WHEN `inventory(spec, aspects)` is called THE SYSTEM SHALL list all K8s
   resources carrying the `codecraftai-run-id` label and emit
   `ProvisionedResource` records with Pod IPs and Service endpoints.

---

### Requirement 6: Node Pool Selection (GPU + IB)

#### Acceptance Criteria

1. WHEN a workload requests `CloudAcceleratorSpec(kind=GPU, model=...)` THE
   SYSTEM SHALL set the Pod's `nodeSelector`/`affinity` to a CoreWeave node
   pool offering that model.
2. WHEN `CloudInterconnect(kind=INFINIBAND_*)` is set THE SYSTEM SHALL add
   the IB-fabric affinity label and request `nvidia.com/hostdev` resources
   (or the CoreWeave-documented equivalent).

---

### Requirement 7: Shared-FS Binding (VAST / WEKA via CSI)

#### Acceptance Criteria

1. WHEN `CloudSharedFilesystem(kind=VAST|WEKA, existing_id=...)` is present
   THE SYSTEM SHALL look up the CSI StorageClass and create a PVC bound to
   the existing volume.
2. WHEN the PVC fails to bind within `aspects.timeout_seconds` THE SYSTEM
   SHALL fail with a timeout error.

---

### Requirement 8: Label Round-Trip Fidelity

#### Acceptance Criteria

1. WHEN translating neutral tags to K8s labels THE SYSTEM SHALL sanitise
   keys/values per Kubernetes rules and emit a warning per change.
2. WHEN reading labels back THE SYSTEM SHALL recover the neutral form so
   round-tripping is the identity for already-K8s-conformant inputs.

---

### Requirement 9: Aspects on Every Call

#### Acceptance Criteria

1. WHEN any provisioner method is invoked THE SYSTEM SHALL accept and
   propagate `Aspects` into both the CoreWeave kubeconfig mint and the K8s
   interop calls.
2. WHEN omitted THE SYSTEM SHALL substitute the default `Aspects()`.
