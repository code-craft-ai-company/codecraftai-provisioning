# Requirements — Proxmox VE Provisioner

## Introduction

The `venue-proxmox` feature provides `codecraftai-provisioning` with the ability to
stand up VMs and LXC containers on Proxmox Virtual Environment.  It implements
the `CloudProvisioner` lifecycle defined in
[cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md) and maps the
neutral resource model in [cloud-resource-model](../cloud-resource-model/design.md)
onto Proxmox primitives via the Proxmox REST API (port 8006, ticket-auth)
surfaced by `codecraftai-interop-proxmox` (built on `codecraftai-restclient-base`).

The venue covers Cluster Network (Linux Bridge or SDN VNet), VM (KVM/QEMU)
clone-from-template, LXC container template clone, Storage (Ceph RBD, ZFS,
LVM-thin, NFS, directory), and the Proxmox firewall.  Proxmox has no native
object storage — `CloudObjectBucket` is a `validate`-error.  Shared FS of
WEKA/Lustre/etc. classes are `validate`-errors except `existing_id` attach via
NFS storage.  No HPC interconnect — `CloudInterconnect(kind != NONE)` is a
`validate`-error.

Every method on `ProxmoxCloudProvisioner` accepts `aspects: Aspects`.

---

## Requirements

### Requirement 1: Validate a Spec

#### Acceptance Criteria

1. WHEN `validate(spec, aspects)` is called THE SYSTEM SHALL ensure every VM/LXC
   has a resolvable target node and storage pool.
2. WHEN the spec contains `CloudObjectBucket`, `CloudLoadBalancer`,
   `CloudInterconnect != NONE`, or unsupported shared-FS kinds THE SYSTEM SHALL
   report errors.
3. WHEN the requested image is neither a template VMID nor a downloadable
   cloud-image URL THE SYSTEM SHALL fail naming the lookup attempted.

---

### Requirement 2: Plan

#### Acceptance Criteria

1. WHEN `plan(spec, aspects)` is called THE SYSTEM SHALL list resources by the
   `codecraftai-run-id` Proxmox tag (Proxmox tags are simple strings).
2. WHEN VM hardware drifts THE SYSTEM SHALL emit `UPDATE` where Proxmox supports
   in-place reconfigure (CPU/RAM hot-plug), otherwise UPDATE-by-recreate.

---

### Requirement 3: Apply Idempotently

#### Acceptance Criteria

1. WHEN `apply(spec, aspects)` is called THE SYSTEM SHALL execute Network
   (bridge/VNet) → Firewall (cluster-level rules) → VM/LXC clone-from-template
   → disk attach → cloud-init config drive → power-on.
2. WHEN re-applying THE SYSTEM SHALL make no mutating calls when every action
   is SKIP.
3. WHEN a VM carries `vpn_join` THE SYSTEM SHALL render the cloud-init snippet
   from [vpn-join-spec](../vpn-join-spec/design.md) into the VM's
   `cicustom` cloud-init `user` snippet (uploaded as a Proxmox snippet).
4. WHEN any DELETE is planned and `aspects.confirm` is false THE SYSTEM SHALL
   raise `ConfirmationRequiredError`.

---

### Requirement 4: Destroy

#### Acceptance Criteria

1. WHEN `destroy(spec, aspects)` is called with confirm THE SYSTEM SHALL stop
   then delete VMs/LXCs, then remove created VNets/bridges.
2. WHEN VPN-joined VMs are deleted THE SYSTEM SHALL invoke
   `IVPNControlPlane.delete_device`.

---

### Requirement 5: Inventory

#### Acceptance Criteria

1. WHEN `inventory(spec, aspects)` is called THE SYSTEM SHALL enumerate VMs/LXCs
   carrying the run-id tag across every cluster node and emit
   `ProvisionedResource` records.

---

### Requirement 6: Tag Round-Trip Fidelity

#### Acceptance Criteria

1. WHEN translating neutral tags to Proxmox tags (semicolon-delimited
   string list per VM) THE SYSTEM SHALL encode each `key=value` pair as a
   single tag.
2. WHEN reading tags back THE SYSTEM SHALL recover the neutral list such that
   round-tripping is the identity.

---

### Requirement 7: Aspects on Every Call

#### Acceptance Criteria

1. WHEN any provisioner method is invoked THE SYSTEM SHALL accept and propagate
   `Aspects`.
2. WHEN omitted THE SYSTEM SHALL substitute the default `Aspects()`.
