# Requirements — DigitalOcean Cloud Provisioner

## Introduction

The `venue-digitalocean` feature provides `codecraftai-provisioning` with the ability
to stand up infrastructure on DigitalOcean.  It implements the `CloudProvisioner`
lifecycle defined in
[cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md) and maps the
neutral resource model in [cloud-resource-model](../cloud-resource-model/design.md)
onto DigitalOcean primitives via the `pydo` SDK surfaced by
`codecraftai-interop-digitalocean`.

The venue covers VPC, Droplet, Cloud Firewall, Block Storage Volume, Spaces (object
storage), and DNS records.  DigitalOcean has **no native shared-filesystem service
of the WEKA/Lustre class** — `CloudSharedFilesystem(kind=LUSTRE|WEKA|VAST|GPFS)`
must fail in `validate` cleanly, and only attach-existing semantics are honoured for
self-hosted NFS realised as a Droplet sized for the role.  Likewise GPU offerings
are limited (H100/H200 single-node SKUs) and DigitalOcean has no high-bandwidth
cluster interconnect — `CloudInterconnect(kind=INFINIBAND_*|EFA|OCI_RDMA)` is a
validate-error.

Every method on `DigitalOceanCloudProvisioner` accepts `aspects: Aspects`.

---

## Requirements

### Requirement 1: Validate a Spec

#### Acceptance Criteria

1. WHEN `validate(spec, aspects)` is called THE SYSTEM SHALL ensure every
   Droplet's `region` is a valid DigitalOcean region slug.
2. WHEN the spec contains `CloudSharedFilesystem(kind in {LUSTRE,WEKA,VAST,GPFS})`
   THE SYSTEM SHALL report an error stating DigitalOcean offers no native
   equivalent and that attach-existing self-hosted NFS is the only supported
   path.
3. WHEN the spec contains `CloudInterconnect(kind != NONE)` THE SYSTEM SHALL
   report an error stating DigitalOcean has no HPC interconnect product.
4. WHEN the spec contains `CloudLoadBalancer` THE SYSTEM SHALL accept it for
   v1.5 stubbing but emit a "not yet implemented" warning today.

---

### Requirement 2: Plan

#### Acceptance Criteria

1. WHEN `plan(spec, aspects)` is called THE SYSTEM SHALL list resources tagged
   with the spec's `codecraftai-run-id` and emit `PlanAction`s.
2. WHEN a Droplet's size or backups setting drifts THE SYSTEM SHALL emit
   `UPDATE`; size changes are UPDATE-by-recreate.
3. WHEN a firewall rule set drifts THE SYSTEM SHALL emit `UPDATE`.

---

### Requirement 3: Apply Idempotently

#### Acceptance Criteria

1. WHEN `apply(spec, aspects)` is called THE SYSTEM SHALL execute VPC →
   firewall → SSH key → Droplet → volume → Spaces → DNS.
2. WHEN re-applying THE SYSTEM SHALL make no mutating calls when every action
   is SKIP.
3. WHEN a Droplet carries `vpn_join` THE SYSTEM SHALL render the cloud-init
   snippet from [vpn-join-spec](../vpn-join-spec/design.md) and pass it as
   `user_data`.
4. WHEN any DELETE is planned and `aspects.confirm` is false THE SYSTEM SHALL
   raise `ConfirmationRequiredError`.

---

### Requirement 4: Destroy

#### Acceptance Criteria

1. WHEN `destroy(spec, aspects)` is called with confirm THE SYSTEM SHALL reverse
   apply order, deleting only run-id-tagged resources.
2. WHEN Droplets carrying `vpn_join` are terminated THE SYSTEM SHALL invoke
   `IVPNControlPlane.delete_device`.

---

### Requirement 5: Inventory

#### Acceptance Criteria

1. WHEN `inventory(spec, aspects)` is called THE SYSTEM SHALL enumerate
   run-id-tagged resources and emit `ProvisionedResource` records with public,
   private (VPC), and overlay addresses.

---

### Requirement 6: Spaces (Object Storage)

#### Acceptance Criteria

1. WHEN `CloudObjectBucket` is present THE SYSTEM SHALL create a Spaces bucket in
   the requested region and tag it with the run-id.
2. WHEN the bucket already exists with matching tags THE SYSTEM SHALL SKIP.

---

### Requirement 7: Tag Round-Trip Fidelity

#### Acceptance Criteria

1. WHEN translating neutral tags to DigitalOcean tags (string list) THE SYSTEM
   SHALL encode each `key=value` pair as a single string tag.
2. WHEN reading tags back THE SYSTEM SHALL recover the original key/value list
   such that round-tripping is the identity for any input.

---

### Requirement 8: Aspects on Every Call

#### Acceptance Criteria

1. WHEN any provisioner method is invoked THE SYSTEM SHALL accept and propagate
   `Aspects`.
2. WHEN omitted THE SYSTEM SHALL substitute the default `Aspects()`.
