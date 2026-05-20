# Requirements — Hetzner Cloud Provisioner

## Introduction

The `venue-hetzner` feature provides `automojo-provisioning` with the ability to
stand up infrastructure on Hetzner Cloud.  It implements the `CloudProvisioner`
lifecycle defined in
[cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md) and maps the
neutral resource model in [cloud-resource-model](../cloud-resource-model/design.md)
onto Hetzner primitives via the `hcloud` SDK surfaced by
`automojo-interop-hetzner`.

The venue covers Network, Server, Firewall, Volume, and DNS records (via the
Hetzner DNS API).  Hetzner Cloud has no native object storage of the S3 class —
`CloudObjectBucket` is a `validate`-error.  Hetzner offers no HPC interconnect —
`CloudInterconnect(kind != NONE)` is a `validate`-error.  GPU offerings are
limited; the resolver only knows the small set Hetzner publishes.

Every method on `HetznerCloudProvisioner` accepts `aspects: Aspects`.

---

## Requirements

### Requirement 1: Validate a Spec

#### Acceptance Criteria

1. WHEN `validate(spec, aspects)` is called THE SYSTEM SHALL ensure every Server's
   `location` resolves to a Hetzner location slug (`nbg1`, `fsn1`, `hel1`,
   `ash`, `hil`, `sin`).
2. WHEN the spec contains `CloudObjectBucket` THE SYSTEM SHALL report an error
   stating Hetzner Cloud offers no native object-storage service in this
   provisioner's scope.
3. WHEN the spec contains `CloudInterconnect(kind != NONE)` or
   `CloudSharedFilesystem(kind in {LUSTRE,WEKA,VAST,GPFS,EFS,FILESTORE})` THE
   SYSTEM SHALL report an error.
4. WHEN an image family is unknown to the resolver THE SYSTEM SHALL fail.

---

### Requirement 2: Plan

#### Acceptance Criteria

1. WHEN `plan(spec, aspects)` is called THE SYSTEM SHALL list resources by the
   `automojo-run-id` label on Servers, Firewalls, Networks, and Volumes.
2. WHEN attributes drift THE SYSTEM SHALL emit `UPDATE`; server type changes are
   UPDATE-by-recreate.

---

### Requirement 3: Apply Idempotently

#### Acceptance Criteria

1. WHEN `apply(spec, aspects)` is called THE SYSTEM SHALL execute Network →
   Firewall → SSH Key → Server → Volume → DNS.
2. WHEN re-applying THE SYSTEM SHALL make no mutating calls when every action is
   SKIP.
3. WHEN a Server carries `vpn_join` THE SYSTEM SHALL render the cloud-init
   snippet from [vpn-join-spec](../vpn-join-spec/design.md) into `user_data`.
4. WHEN any DELETE is planned and `aspects.confirm` is false THE SYSTEM SHALL
   raise `ConfirmationRequiredError`.

---

### Requirement 4: Destroy

#### Acceptance Criteria

1. WHEN `destroy(spec, aspects)` is called with confirm THE SYSTEM SHALL reverse
   apply order.
2. WHEN VPN-joined Servers are deleted THE SYSTEM SHALL invoke
   `IVPNControlPlane.delete_device`.

---

### Requirement 5: Inventory

#### Acceptance Criteria

1. WHEN `inventory(spec, aspects)` is called THE SYSTEM SHALL enumerate
   run-id-labelled resources and emit `ProvisionedResource` records.

---

### Requirement 6: Tag/Label Round-Trip Fidelity

#### Acceptance Criteria

1. WHEN translating neutral tags to Hetzner labels (key/value dict) THE SYSTEM
   SHALL preserve every key/value verbatim within Hetzner's label rules.
2. WHEN a label key or value violates Hetzner's character rules THE SYSTEM SHALL
   fail in `validate`.
3. WHEN reading labels back THE SYSTEM SHALL recover the neutral form so that
   conformant inputs round-trip as identity.

---

### Requirement 7: Aspects on Every Call

#### Acceptance Criteria

1. WHEN any provisioner method is invoked THE SYSTEM SHALL accept and propagate
   `Aspects`.
2. WHEN omitted THE SYSTEM SHALL substitute the default `Aspects()`.
