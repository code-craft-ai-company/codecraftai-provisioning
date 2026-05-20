# Requirements — Vultr Cloud Provisioner

## Introduction

The `venue-vultr` feature provides `automojo-provisioning` with the ability to
stand up infrastructure on Vultr.  It implements the `CloudProvisioner` lifecycle
defined in
[cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md) and maps the
neutral resource model in [cloud-resource-model](../cloud-resource-model/design.md)
onto Vultr primitives via the Vultr REST API surfaced by `automojo-interop-vultr`
(no first-party Python SDK; the interop layer builds on
`automojo-restclient-base`).

The venue covers VPC (`vpc2`), Instance, Cloud Firewall, Block Storage, Object
Storage, and DNS records.  GPU SKUs are limited (A16/A40/L40S single-node);
the resolver lists what Vultr publishes.  Vultr has no HPC interconnect —
`CloudInterconnect(kind != NONE)` is a `validate`-error.  Vultr has no
shared-FS service of the WEKA/Lustre class — those are `validate`-errors.

Every method on `VultrCloudProvisioner` accepts `aspects: Aspects`.

---

## Requirements

### Requirement 1: Validate a Spec

#### Acceptance Criteria

1. WHEN `validate(spec, aspects)` is called THE SYSTEM SHALL ensure every
   Instance's `region` resolves to a Vultr region slug.
2. WHEN the spec contains `CloudInterconnect(kind != NONE)` or
   `CloudSharedFilesystem(kind in {LUSTRE,WEKA,VAST,GPFS,EFS,FILESTORE})` THE
   SYSTEM SHALL report an error.
3. WHEN an OS family is unknown to the resolver THE SYSTEM SHALL fail.

---

### Requirement 2: Plan

#### Acceptance Criteria

1. WHEN `plan(spec, aspects)` is called THE SYSTEM SHALL list resources by
   the `automojo-run-id` tag and emit `PlanAction`s.
2. WHEN plan or backups setting drifts THE SYSTEM SHALL emit `UPDATE`; plan
   changes are UPDATE-by-recreate.

---

### Requirement 3: Apply Idempotently

#### Acceptance Criteria

1. WHEN `apply(spec, aspects)` is called THE SYSTEM SHALL execute VPC →
   Firewall Group → SSH Key → Instance → Block Storage → Object Storage → DNS.
2. WHEN re-applying THE SYSTEM SHALL make no mutating calls when every action
   is SKIP.
3. WHEN an Instance carries `vpn_join` THE SYSTEM SHALL render the cloud-init
   snippet from [vpn-join-spec](../vpn-join-spec/design.md) into the
   `user_data` body (base64-encoded as Vultr requires).
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

### Requirement 6: Tag Round-Trip Fidelity

#### Acceptance Criteria

1. WHEN translating neutral tags to Vultr tags (string list) THE SYSTEM SHALL
   encode each `key=value` pair as a single string tag.
2. WHEN reading tags back THE SYSTEM SHALL recover the neutral list such that
   round-tripping is the identity.

---

### Requirement 7: Aspects on Every Call

#### Acceptance Criteria

1. WHEN any provisioner method is invoked THE SYSTEM SHALL accept and propagate
   `Aspects`.
2. WHEN omitted THE SYSTEM SHALL substitute the default `Aspects()`.
