# Requirements — GCP Cloud Provisioner

## Introduction

The `venue-gcp` feature provides `codecraftai-provisioning` with the ability to stand
up infrastructure on Google Cloud Platform.  It implements the `CloudProvisioner`
lifecycle defined in
[cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md) and maps the
neutral resource model in [cloud-resource-model](../cloud-resource-model/design.md)
onto GCP primitives via the `google-cloud-*` SDKs surfaced by
`codecraftai-interop-gcp`.

The venue covers VPC (`compute.networks`), Subnet, Firewall rule, Compute Engine
Instance, Persistent Disk, GCS bucket, and Cloud DNS record.  It additionally
honours the §7.1 extensions: GPU resolution for the A3-Mega/A3-Ultra families, TPU
provisioning (a distinct resource type, not a VM accelerator) via
`tpu_v2.NodeServiceClient`, compact placement policy for tightly-coupled training,
and shared FS realised as either Filestore or Parallelstore depending on
performance class.

Every method on `GcpCloudProvisioner` accepts an `aspects: Aspects` parameter.

---

## Requirements

### Requirement 1: Validate a Spec

**User Story:** As a coordinator, I want GCP-specific validation to run before
apply.

#### Acceptance Criteria

1. WHEN `validate(spec, aspects)` is called THE SYSTEM SHALL ensure every resource
   has a resolvable region/zone.
2. WHEN the spec contains `CloudInterconnect(kind=EFA)` or `kind=INFINIBAND_*` THE
   SYSTEM SHALL report an error stating that GCP exposes compact placement policy
   and GPUDirect-TCPX/RDMA, not EFA or raw InfiniBand SKUs.
3. WHEN the spec contains `CloudSharedFilesystem(kind=WEKA)` or `kind=LUSTRE` THE
   SYSTEM SHALL map `LUSTRE` to Parallelstore and reject `WEKA` with a
   substitution suggestion.
4. WHEN a TPU resource is requested with no `accelerator_type` (e.g. `TPU_V5P`)
   THE SYSTEM SHALL fail.

---

### Requirement 2: Plan a Spec

**User Story:** As a coordinator, I want a diff against the live project.

#### Acceptance Criteria

1. WHEN `plan(spec, aspects)` is called THE SYSTEM SHALL list every resource by
   `codecraftai-run-id` label and emit `PlanAction`s.
2. WHEN labels or firewall rule sets drift THE SYSTEM SHALL emit `UPDATE`.
3. WHEN a resource is absent THE SYSTEM SHALL emit `CREATE`.

---

### Requirement 3: Apply Idempotently

**User Story:** As a coordinator, I want apply to be re-runnable.

#### Acceptance Criteria

1. WHEN `apply(spec, aspects)` is called THE SYSTEM SHALL execute in the order
   network → subnet → firewall → instance → PD → TPU → GCS → DNS.
2. WHEN re-applying an already-applied spec THE SYSTEM SHALL make no mutating
   calls.
3. WHEN an instance carries `vpn_join` THE SYSTEM SHALL render the cloud-init
   snippet from [vpn-join-spec](../vpn-join-spec/design.md) and put it in the
   instance's `metadata.items["user-data"]`.
4. WHEN `aspects.confirm` is false and any DELETE is planned THE SYSTEM SHALL
   raise `ConfirmationRequiredError`.

---

### Requirement 4: Destroy

**User Story:** As a coordinator, I want destroy to clean up only run-id resources.

#### Acceptance Criteria

1. WHEN `destroy(spec, aspects)` is called with confirm THE SYSTEM SHALL reverse
   apply order and delete only resources carrying the run-id label.
2. WHEN VPN-joined instances are terminated THE SYSTEM SHALL invoke
   `IVPNControlPlane.delete_device`.

---

### Requirement 5: Inventory

#### Acceptance Criteria

1. WHEN `inventory(spec, aspects)` is called THE SYSTEM SHALL enumerate run-id
   resources and emit `ProvisionedResource` records with public IP, internal IP,
   and overlay IP when known.

---

### Requirement 6: Compact Placement Policy

**User Story:** As a coordinator, I want compact placement for A3 training
clusters.

#### Acceptance Criteria

1. WHEN multiple instances share `interconnect_group` and their accelerators
   resolve to A3-Mega or A3-Ultra THE SYSTEM SHALL create a compact
   `ResourcePolicy` and attach every instance to it.
2. WHEN the resolved zone does not support compact placement for the family THE
   SYSTEM SHALL fail in `validate`.

---

### Requirement 7: TPU Resource Type

**User Story:** As a coordinator, I want TPU pods modelled as a first-class
accelerator.

#### Acceptance Criteria

1. WHEN `CloudAcceleratorSpec(kind=TPU, model="TPU_V5P", count=N)` is present THE
   SYSTEM SHALL provision a TPU node via `tpu_v2.NodeServiceClient.create_node`,
   not a Compute Engine VM.
2. WHEN the TPU node is created THE SYSTEM SHALL emit it in inventory with kind
   `tpu` and the assigned host IPs.
3. WHEN a TPU spec also asks for `subnet` from a VPC the TPU API rejects THE
   SYSTEM SHALL fail in `validate`.

---

### Requirement 8: Filestore / Parallelstore Shared FS

#### Acceptance Criteria

1. WHEN `CloudSharedFilesystem(kind=LUSTRE, existing_id=...)` is supplied THE
   SYSTEM SHALL look up the Parallelstore instance and add cloud-init mounts.
2. WHEN `CloudSharedFilesystem(kind=FILESTORE, existing_id=...)` is supplied THE
   SYSTEM SHALL mount via NFSv3 from the Filestore tier.
3. WHEN `existing_id` is absent THE SYSTEM SHALL fail per §7.6.

---

### Requirement 9: Tag/Label Round-Trip Fidelity

#### Acceptance Criteria

1. WHEN translating neutral tags to GCP labels THE SYSTEM SHALL lowercase keys
   and replace illegal characters per GCP label rules, emitting a warning per
   change.
2. WHEN reading labels back THE SYSTEM SHALL reconstruct the neutral form so that
   already-GCP-conformant tag sets round-trip as identity.

---

### Requirement 10: Aspects on Every Call

#### Acceptance Criteria

1. WHEN any provisioner method is invoked THE SYSTEM SHALL accept and propagate
   `Aspects`.
2. WHEN omitted THE SYSTEM SHALL use the default `Aspects()`.
