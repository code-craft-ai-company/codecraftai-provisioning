# Requirements — Crusoe Cloud Provisioner

## Introduction

The `venue-crusoe` feature provides `automojo-provisioning` with the ability to
stand up GPU infrastructure on Crusoe Cloud.  It implements the
`CloudProvisioner` lifecycle defined in
[cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md) and maps the
neutral resource model in [cloud-resource-model](../cloud-resource-model/design.md)
onto Crusoe primitives via the Crusoe Cloud REST API
(`api.crusoecloud.com/v1alpha5/`) surfaced by `automojo-interop-crusoe` (built
on `automojo-restclient-base`).

Crusoe's API shape is the closest to AWS in this group: VPCs, Subnets,
Firewall Rules, Instances, Disks, IB-enabled placement.  GPU SKUs cover H100,
H200, B200, and L40S families; InfiniBand-enabled placement is realised by
specifying `ib_partition_id` on instance create.  Crusoe offers managed file
storage (`storage_disks` with file-system option) — attach-only in v1 per
§7.6.  No native object storage, no LB — `validate`-errors.

Every method on `CrusoeCloudProvisioner` accepts `aspects: Aspects`.

---

## Requirements

### Requirement 1: Validate a Spec

#### Acceptance Criteria

1. WHEN `validate(spec, aspects)` is called THE SYSTEM SHALL ensure every
   Instance has a resolvable Crusoe `location` and `instance_type`.
2. WHEN `CloudInterconnect(kind=INFINIBAND_*)` is requested but the resolved
   instance_type is not IB-eligible THE SYSTEM SHALL fail.
3. WHEN the spec contains `CloudObjectBucket` or `CloudLoadBalancer` THE
   SYSTEM SHALL report errors.
4. WHEN `CloudSharedFilesystem(kind != VENUE_NATIVE)` is supplied without
   `existing_id` THE SYSTEM SHALL fail.

---

### Requirement 2: Plan

#### Acceptance Criteria

1. WHEN `plan(spec, aspects)` is called THE SYSTEM SHALL list resources by
   `automojo-run-id` label and emit `PlanAction`s.
2. WHEN instance_type drifts THE SYSTEM SHALL flag UPDATE-by-recreate.

---

### Requirement 3: Apply Idempotently

#### Acceptance Criteria

1. WHEN `apply(spec, aspects)` is called THE SYSTEM SHALL execute VPC →
   Subnet → Firewall Rules → SSH Keys → IB Partition (if needed) →
   Instances → Disks → File-system attach.
2. WHEN re-applying THE SYSTEM SHALL make no mutating calls when every action
   is SKIP.
3. WHEN an Instance carries `vpn_join` THE SYSTEM SHALL render the cloud-init
   snippet from [vpn-join-spec](../vpn-join-spec/design.md) into the launch
   request's `user_data`.
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

### Requirement 6: IB Partition Resolution

#### Acceptance Criteria

1. WHEN multiple Instances share `interconnect_group` with
   `CloudInterconnect(kind=INFINIBAND_*)` THE SYSTEM SHALL create or reuse a
   Crusoe IB Partition and attach every instance to it via
   `ib_partition_id`.
2. WHEN an IB Partition is created THE SYSTEM SHALL tag it with the run-id.

---

### Requirement 7: Tag/Label Round-Trip Fidelity

#### Acceptance Criteria

1. WHEN translating neutral tags to Crusoe labels (dict) THE SYSTEM SHALL
   preserve every key/value verbatim within Crusoe's label rules.
2. WHEN reading labels back THE SYSTEM SHALL recover the neutral form such
   that round-tripping is the identity for conformant inputs.

---

### Requirement 8: Aspects on Every Call

#### Acceptance Criteria

1. WHEN any provisioner method is invoked THE SYSTEM SHALL accept and
   propagate `Aspects`.
2. WHEN omitted THE SYSTEM SHALL substitute the default `Aspects()`.
