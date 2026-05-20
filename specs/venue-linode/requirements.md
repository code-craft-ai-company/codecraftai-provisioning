# Requirements — Linode (Akamai Cloud) Provisioner

## Introduction

The `venue-linode` feature provides `automojo-provisioning` with the ability to
stand up infrastructure on Linode (Akamai Connected Cloud).  It implements the
`CloudProvisioner` lifecycle defined in
[cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md) and maps the
neutral resource model in [cloud-resource-model](../cloud-resource-model/design.md)
onto Linode primitives via the `linode_api4` SDK surfaced by
`automojo-interop-linode`.

The venue covers VPC, Instance (Linode), Cloud Firewall, Block Storage Volume,
Object Storage, and Domain records.  GPU offerings are limited (RTX 4000 / RTX
6000 SKUs); the resolver lists what Linode publishes.  Linode has no HPC
interconnect — `CloudInterconnect(kind != NONE)` is a `validate`-error.  Linode
has no shared-FS service of the WEKA/Lustre class — those are `validate`-errors.

Every method on `LinodeCloudProvisioner` accepts `aspects: Aspects`.

---

## Requirements

### Requirement 1: Validate a Spec

#### Acceptance Criteria

1. WHEN `validate(spec, aspects)` is called THE SYSTEM SHALL ensure every Linode's
   `region` resolves to a Linode region slug.
2. WHEN the spec contains `CloudInterconnect(kind != NONE)` or
   `CloudSharedFilesystem(kind in {LUSTRE,WEKA,VAST,GPFS,EFS,FILESTORE})` THE
   SYSTEM SHALL report an error.
3. WHEN an image family is unknown to the resolver THE SYSTEM SHALL fail.

---

### Requirement 2: Plan

#### Acceptance Criteria

1. WHEN `plan(spec, aspects)` is called THE SYSTEM SHALL list resources by the
   `automojo-run-id` tag on Instances, Firewalls, VPCs, and Volumes.
2. WHEN attributes drift THE SYSTEM SHALL emit `UPDATE`; type changes are
   UPDATE-by-resize when Linode allows it, otherwise UPDATE-by-recreate.

---

### Requirement 3: Apply Idempotently

#### Acceptance Criteria

1. WHEN `apply(spec, aspects)` is called THE SYSTEM SHALL execute VPC →
   Firewall → SSH Key (via account-level Stack metadata) → Instance → Volume →
   Object Storage → DNS.
2. WHEN re-applying THE SYSTEM SHALL make no mutating calls when every action is
   SKIP.
3. WHEN an Instance carries `vpn_join` THE SYSTEM SHALL render the cloud-init
   snippet from [vpn-join-spec](../vpn-join-spec/design.md) into the
   `metadata.user_data` field (StackScript or cloud-init based on image
   capability).
4. WHEN any DELETE is planned and `aspects.confirm` is false THE SYSTEM SHALL
   raise `ConfirmationRequiredError`.

---

### Requirement 4: Destroy

#### Acceptance Criteria

1. WHEN `destroy(spec, aspects)` is called with confirm THE SYSTEM SHALL reverse
   apply order.
2. WHEN VPN-joined Instances are deleted THE SYSTEM SHALL invoke
   `IVPNControlPlane.delete_device`.

---

### Requirement 5: Inventory

#### Acceptance Criteria

1. WHEN `inventory(spec, aspects)` is called THE SYSTEM SHALL enumerate
   run-id-tagged resources and emit `ProvisionedResource` records.

---

### Requirement 6: Object Storage

#### Acceptance Criteria

1. WHEN `CloudObjectBucket` is present THE SYSTEM SHALL create the bucket in the
   requested object-storage cluster (`us-east-1`, `eu-central-1`, etc.).
2. WHEN the bucket already exists THE SYSTEM SHALL SKIP.

---

### Requirement 7: Tag Round-Trip Fidelity

#### Acceptance Criteria

1. WHEN translating neutral tags to Linode tags (string list) THE SYSTEM SHALL
   encode each `key=value` pair as a single string tag.
2. WHEN reading tags back THE SYSTEM SHALL recover the original list such that
   round-tripping is the identity.

---

### Requirement 8: Aspects on Every Call

#### Acceptance Criteria

1. WHEN any provisioner method is invoked THE SYSTEM SHALL accept and propagate
   `Aspects`.
2. WHEN omitted THE SYSTEM SHALL substitute the default `Aspects()`.
