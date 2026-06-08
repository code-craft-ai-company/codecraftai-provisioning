# Requirements — Equinix Metal (bare metal) Provisioner

## Introduction

The `venue-equinix-metal` feature provides `codecraftai-provisioning` with the ability
to provision **bare-metal** infrastructure on Equinix Metal.  It implements the
`CloudProvisioner` lifecycle defined in
[cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md) and maps the
neutral resource model in [cloud-resource-model](../cloud-resource-model/design.md)
onto Equinix Metal primitives via the `packet-python` SDK surfaced by
`codecraftai-interop-equinix-metal`.

The venue covers Projects (apex container), Project SSH Keys, VLANs and Layer-2
networks, IP Reservations, and **Devices** (bare-metal servers).  Equinix Metal
has no native object storage in its Metal product — `CloudObjectBucket` is a
`validate`-error.  Equinix Fabric provides inter-region/inter-cloud
interconnects (not RDMA between Devices in the same metro); HPC-class RDMA
interconnects (`CloudInterconnect(kind=INFINIBAND_*|EFA|OCI_RDMA)`) are
`validate`-errors.  Block storage is a separately-priced offering not part of
v1; `CloudStorageVolume` is treated as attach-existing or `validate`-error.

Every method on `EquinixMetalCloudProvisioner` accepts `aspects: Aspects`.

---

## Requirements

### Requirement 1: Validate a Spec

#### Acceptance Criteria

1. WHEN `validate(spec, aspects)` is called THE SYSTEM SHALL ensure every Device's
   `metro` resolves to an Equinix metro slug.
2. WHEN the spec contains `CloudObjectBucket` THE SYSTEM SHALL report an error
   stating Metal has no native object storage.
3. WHEN the spec contains `CloudInterconnect(kind != NONE)` or
   `CloudSharedFilesystem(kind != VENUE_NATIVE)` THE SYSTEM SHALL report an
   error.
4. WHEN the requested `plan` (Metal SKU) is unknown to the resolver THE SYSTEM
   SHALL fail.

---

### Requirement 2: Plan

#### Acceptance Criteria

1. WHEN `plan(spec, aspects)` is called THE SYSTEM SHALL list resources by the
   `codecraftai-run-id` tag and emit `PlanAction`s.
2. WHEN device hostname or tags drift THE SYSTEM SHALL emit `UPDATE`; plan
   changes are UPDATE-by-recreate.

---

### Requirement 3: Apply Idempotently

#### Acceptance Criteria

1. WHEN `apply(spec, aspects)` is called THE SYSTEM SHALL execute Project
   verification → VLAN → IP Reservation → SSH Key → Device → DNS (if any).
2. WHEN re-applying THE SYSTEM SHALL make no mutating calls when every action
   is SKIP.
3. WHEN a Device carries `vpn_join` THE SYSTEM SHALL render the cloud-init
   snippet from [vpn-join-spec](../vpn-join-spec/design.md) into the Device's
   `userdata` field.
4. WHEN any DELETE is planned and `aspects.confirm` is false THE SYSTEM SHALL
   raise `ConfirmationRequiredError`.

---

### Requirement 4: Destroy

#### Acceptance Criteria

1. WHEN `destroy(spec, aspects)` is called with confirm THE SYSTEM SHALL reverse
   apply order: Devices → IP Reservations → VLANs.
2. WHEN VPN-joined Devices are deleted THE SYSTEM SHALL invoke
   `IVPNControlPlane.delete_device`.

---

### Requirement 5: Inventory

#### Acceptance Criteria

1. WHEN `inventory(spec, aspects)` is called THE SYSTEM SHALL enumerate
   run-id-tagged resources and emit `ProvisionedResource` records.

---

### Requirement 6: Tag Round-Trip Fidelity

#### Acceptance Criteria

1. WHEN translating neutral tags to Metal device tags (string list) THE SYSTEM
   SHALL encode each `key=value` pair as a single tag.
2. WHEN reading tags back THE SYSTEM SHALL recover the neutral list such that
   round-tripping is the identity.

---

### Requirement 7: Aspects on Every Call

#### Acceptance Criteria

1. WHEN any provisioner method is invoked THE SYSTEM SHALL accept and propagate
   `Aspects`.
2. WHEN omitted THE SYSTEM SHALL substitute the default `Aspects()`.
