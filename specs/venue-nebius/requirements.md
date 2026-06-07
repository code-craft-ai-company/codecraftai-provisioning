# Requirements — Nebius Provisioner

## Introduction

The `venue-nebius` feature provides `codecraftai-provisioning` with the ability to
stand up GPU infrastructure on Nebius.  It implements the `CloudProvisioner`
lifecycle defined in
[cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md) and maps the
neutral resource model in [cloud-resource-model](../cloud-resource-model/design.md)
onto Nebius primitives via the Nebius REST API surfaced by
`codecraftai-interop-nebius` (built on `codecraftai-restclient-base`).

Nebius's product shape is similar to Crusoe — VPCs, subnets, security groups,
instances, disks, **GPU clusters** (their IB-enabled placement primitive),
and native managed file storage.  Nebius offers managed object storage; the
provisioner honours `CloudObjectBucket`.  No native LB (v1).  Shared FS
attach-only in v1 per §7.6.

Every method on `NebiusCloudProvisioner` accepts `aspects: Aspects`.

---

## Requirements

### Requirement 1: Validate a Spec

#### Acceptance Criteria

1. WHEN `validate(spec, aspects)` is called THE SYSTEM SHALL ensure every
   resource is anchored to a Nebius `parent_id` (project/folder).
2. WHEN `CloudInterconnect(kind=INFINIBAND_*)` is requested but the resolved
   platform is not IB-eligible THE SYSTEM SHALL fail.
3. WHEN `CloudLoadBalancer` is requested THE SYSTEM SHALL report a v1
   "not yet supported" error.
4. WHEN `CloudSharedFilesystem` is supplied without `existing_id` THE SYSTEM
   SHALL fail.

---

### Requirement 2: Plan

#### Acceptance Criteria

1. WHEN `plan(spec, aspects)` is called THE SYSTEM SHALL list resources by
   `codecraftai-run-id` label and emit `PlanAction`s.
2. WHEN instance platform/preset drifts THE SYSTEM SHALL flag
   UPDATE-by-recreate.

---

### Requirement 3: Apply Idempotently

#### Acceptance Criteria

1. WHEN `apply(spec, aspects)` is called THE SYSTEM SHALL execute VPC →
   Subnet → Security Group → SSH keys → GPU cluster (if needed) →
   Instances → Disks → File-storage attach → Object Storage bucket → DNS.
2. WHEN re-applying THE SYSTEM SHALL make no mutating calls when every action
   is SKIP.
3. WHEN an Instance carries `vpn_join` THE SYSTEM SHALL render the cloud-init
   snippet from [vpn-join-spec](../vpn-join-spec/design.md) into the
   Instance's `metadata["user-data"]`.
4. WHEN any DELETE is planned and `aspects.confirm` is false THE SYSTEM SHALL
   raise `ConfirmationRequiredError`.

---

### Requirement 4: Destroy

#### Acceptance Criteria

1. WHEN `destroy(spec, aspects)` is called with confirm THE SYSTEM SHALL
   reverse apply order.
2. WHEN VPN-joined Instances are terminated THE SYSTEM SHALL invoke
   `IVPNControlPlane.delete_device`.

---

### Requirement 5: Inventory

#### Acceptance Criteria

1. WHEN `inventory(spec, aspects)` is called THE SYSTEM SHALL enumerate
   run-id-labelled resources and emit `ProvisionedResource` records.

---

### Requirement 6: GPU Cluster (IB Placement)

#### Acceptance Criteria

1. WHEN multiple Instances share `interconnect_group` with
   `CloudInterconnect(kind=INFINIBAND_*)` THE SYSTEM SHALL create or reuse a
   Nebius GPU Cluster and place every Instance in it.
2. WHEN the requested platform has no GPU Cluster support THE SYSTEM SHALL
   fail in `validate`.

---

### Requirement 7: Tag/Label Round-Trip Fidelity

#### Acceptance Criteria

1. WHEN translating neutral tags to Nebius labels THE SYSTEM SHALL preserve
   every key/value verbatim within Nebius rules.
2. WHEN reading back THE SYSTEM SHALL recover the neutral form so
   round-tripping is the identity for conformant inputs.

---

### Requirement 8: Aspects on Every Call

#### Acceptance Criteria

1. WHEN any provisioner method is invoked THE SYSTEM SHALL accept and
   propagate `Aspects`.
2. WHEN omitted THE SYSTEM SHALL substitute the default `Aspects()`.
