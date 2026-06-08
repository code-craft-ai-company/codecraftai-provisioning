# Requirements — libvirt / KVM Provisioner

## Introduction

The `venue-libvirt` feature provides `codecraftai-provisioning` with the ability to
stand up VMs on a single libvirt host or a small farm.  It implements the
`CloudProvisioner` lifecycle defined in
[cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md) and maps the
neutral resource model in [cloud-resource-model](../cloud-resource-model/design.md)
onto libvirt primitives via the `libvirt-python` bindings surfaced by
`codecraftai-interop-libvirt` (not REST — native bindings; the bindings are wrapped
behind a connection-pool abstraction).

The venue covers Network (libvirt `network` XML, NAT or bridged), Storage Pool
(`dir`, `nfs`, `lvm`), Volume, Domain (VM) defined from a cloud-image with
cloud-init seed ISO.  libvirt has no native object storage, load balancer, HPC
interconnect, or managed shared FS — those are `validate`-errors.  The
provisioner is intentionally single-host-friendly: clustering is left to higher
layers (or upgrade to Proxmox/oVirt).

Every method on `LibvirtCloudProvisioner` accepts `aspects: Aspects`.

---

## Requirements

### Requirement 1: Validate a Spec

#### Acceptance Criteria

1. WHEN `validate(spec, aspects)` is called THE SYSTEM SHALL ensure every Domain
   has a resolvable libvirt connection URI and storage pool.
2. WHEN the spec contains `CloudObjectBucket`, `CloudLoadBalancer`,
   `CloudInterconnect != NONE`, or any `CloudSharedFilesystem` without
   `existing_id` THE SYSTEM SHALL report errors.
3. WHEN the requested image is not present in the configured base-image pool
   THE SYSTEM SHALL fail naming the lookup attempted.

---

### Requirement 2: Plan

#### Acceptance Criteria

1. WHEN `plan(spec, aspects)` is called THE SYSTEM SHALL list Domains, Networks,
   and Volumes whose metadata contains the `codecraftai-run-id` element.
2. WHEN Domain XML drifts (vCPUs, memory, disk count) THE SYSTEM SHALL emit
   `UPDATE` where libvirt supports live edit, otherwise UPDATE-by-recreate.

---

### Requirement 3: Apply Idempotently

#### Acceptance Criteria

1. WHEN `apply(spec, aspects)` is called THE SYSTEM SHALL execute Network
   define+start → Storage Pool define+start → base-image volume clone (qcow2
   backing chain) → cloud-init seed ISO build+upload → Domain define+start.
2. WHEN re-applying THE SYSTEM SHALL make no mutating calls when every action
   is SKIP.
3. WHEN a Domain carries `vpn_join` THE SYSTEM SHALL render the cloud-init
   snippet from [vpn-join-spec](../vpn-join-spec/design.md) into the seed
   ISO's `user-data`.
4. WHEN any DELETE is planned and `aspects.confirm` is false THE SYSTEM SHALL
   raise `ConfirmationRequiredError`.

---

### Requirement 4: Destroy

#### Acceptance Criteria

1. WHEN `destroy(spec, aspects)` is called with confirm THE SYSTEM SHALL
   destroy then undefine Domains, delete cloned Volumes, and undefine Networks
   created by the run.
2. WHEN VPN-joined Domains are destroyed THE SYSTEM SHALL invoke
   `IVPNControlPlane.delete_device`.

---

### Requirement 5: Inventory

#### Acceptance Criteria

1. WHEN `inventory(spec, aspects)` is called THE SYSTEM SHALL enumerate
   run-id-tagged Domains and emit `ProvisionedResource` records using the
   QEMU guest agent (when present) for IP discovery.

---

### Requirement 6: Run-ID Metadata Encoding

**User Story:** As a coordinator, I want libvirt's lack of tags handled
deterministically, so plan and inventory queries are reliable.

#### Acceptance Criteria

1. WHEN translating neutral tags THE SYSTEM SHALL embed them inside the Domain
   XML `<metadata><ccai:tags>...</ccai:tags></metadata>` block using
   the namespace `https://code-craft.ai/provisioning/v1`.
2. WHEN reading Domain XML back THE SYSTEM SHALL recover the neutral tag list
   such that round-tripping is the identity.

---

### Requirement 7: Aspects on Every Call

#### Acceptance Criteria

1. WHEN any provisioner method is invoked THE SYSTEM SHALL accept and propagate
   `Aspects`.
2. WHEN omitted THE SYSTEM SHALL substitute the default `Aspects()`.
