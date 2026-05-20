# Requirements — Oracle Cloud Infrastructure (OCI) Provisioner

## Introduction

The `venue-oracle` feature provides `automojo-provisioning` with the ability to
stand up infrastructure on Oracle Cloud Infrastructure.  It implements the
`CloudProvisioner` lifecycle defined in
[cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md) and maps the
neutral resource model in [cloud-resource-model](../cloud-resource-model/design.md)
onto OCI primitives via the `oci` SDK surfaced by `automojo-interop-oracle`.

The venue covers VCN (Virtual Cloud Network), Subnet, Security List (and
optionally Network Security Groups), Compute Instance, Block Volume, Object
Storage bucket, and DNS records.  OCI's HPC differentiator is the **cluster
network** — RoCEv2 RDMA fabric at up to 3,200 Gbps — which realises
`CloudInterconnect(kind=OCI_RDMA, topology=RAIL_OPTIMIZED|FAT_TREE)`.  Shared FS
is realised through OCI File Storage (`CloudSharedFilesystem(kind=VENUE_NATIVE)`
or attach by `existing_id` for `kind=LUSTRE` when a managed Lustre offering is
selected).

Every method on `OracleCloudProvisioner` accepts `aspects: Aspects`.

---

## Requirements

### Requirement 1: Validate a Spec

#### Acceptance Criteria

1. WHEN `validate(spec, aspects)` is called THE SYSTEM SHALL ensure every
   Instance has a resolvable compartment OCID and availability domain.
2. WHEN the spec contains `CloudInterconnect(kind=EFA|INFINIBAND_*)` THE SYSTEM
   SHALL report an error stating OCI exposes RDMA only via `OCI_RDMA` cluster
   networks.
3. WHEN the spec contains `CloudInterconnect(kind=OCI_RDMA)` and the resolved
   shape is not a BM.GPU shape THE SYSTEM SHALL fail naming the shape.
4. WHEN `CloudSharedFilesystem(kind=WEKA)` is requested THE SYSTEM SHALL fail
   with a substitution suggestion (File Storage or attach-existing).

---

### Requirement 2: Plan

#### Acceptance Criteria

1. WHEN `plan(spec, aspects)` is called THE SYSTEM SHALL list resources by the
   `automojo-run-id` freeform tag and emit `PlanAction`s.
2. WHEN security-list rules drift THE SYSTEM SHALL emit `UPDATE`.

---

### Requirement 3: Apply Idempotently

#### Acceptance Criteria

1. WHEN `apply(spec, aspects)` is called THE SYSTEM SHALL execute VCN → Subnet
   → Internet/NAT Gateway + Route Table → Security List → Cluster Network (if
   any) → Instance → Block Volume → File Storage attach → Object Storage → DNS.
2. WHEN re-applying THE SYSTEM SHALL make no mutating calls when every action
   is SKIP.
3. WHEN an Instance carries `vpn_join` THE SYSTEM SHALL render the cloud-init
   snippet from [vpn-join-spec](../vpn-join-spec/design.md) into the Instance's
   `metadata["user_data"]` (base64-encoded).
4. WHEN any DELETE is planned and `aspects.confirm` is false THE SYSTEM SHALL
   raise `ConfirmationRequiredError`.

---

### Requirement 4: Destroy

#### Acceptance Criteria

1. WHEN `destroy(spec, aspects)` is called with confirm THE SYSTEM SHALL reverse
   apply order.
2. WHEN VPN-joined Instances are terminated THE SYSTEM SHALL invoke
   `IVPNControlPlane.delete_device`.

---

### Requirement 5: Inventory

#### Acceptance Criteria

1. WHEN `inventory(spec, aspects)` is called THE SYSTEM SHALL enumerate
   run-id-tagged resources and emit `ProvisionedResource` records.

---

### Requirement 6: Cluster Network (RDMA)

**User Story:** As a coordinator standing up an OCI GPU training pod, I want the
provisioner to create a Cluster Network and place instances inside it.

#### Acceptance Criteria

1. WHEN multiple instances share `interconnect_group` with
   `CloudInterconnect(kind=OCI_RDMA)` THE SYSTEM SHALL create or reuse a Cluster
   Network with the appropriate topology and add every instance to it.
2. WHEN the Cluster Network creation fails because the requested shape is not
   available in the AD THE SYSTEM SHALL surface the capacity error verbatim.
3. WHEN the spec asks for a non-RDMA shape inside an RDMA cluster network THE
   SYSTEM SHALL fail in `validate`.

---

### Requirement 7: File Storage Shared FS

#### Acceptance Criteria

1. WHEN `CloudSharedFilesystem(kind=VENUE_NATIVE)` or
   `kind=LUSTRE, existing_id=...` is supplied THE SYSTEM SHALL create or
   reuse a File Storage mount target and add cloud-init mounts.
2. WHEN `kind=LUSTRE` is supplied without `existing_id` THE SYSTEM SHALL fail
   per §7.6.

---

### Requirement 8: Tag Round-Trip Fidelity

#### Acceptance Criteria

1. WHEN translating neutral tags to OCI freeform tags THE SYSTEM SHALL preserve
   every key/value verbatim.
2. WHEN reading freeform tags back THE SYSTEM SHALL reconstruct the neutral form
   so round-tripping is the identity.

---

### Requirement 9: Aspects on Every Call

#### Acceptance Criteria

1. WHEN any provisioner method is invoked THE SYSTEM SHALL accept and propagate
   `Aspects`.
2. WHEN omitted THE SYSTEM SHALL substitute the default `Aspects()`.
