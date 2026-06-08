# Requirements — XCP-ng / XenServer Provisioner

## Introduction

The `venue-xcpng` feature provides `codecraftai-provisioning` with the ability to
stand up VMs on XCP-ng or Citrix Hypervisor (XenServer) pools.  It implements
the `CloudProvisioner` lifecycle defined in
[cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md) and maps the
neutral resource model in [cloud-resource-model](../cloud-resource-model/design.md)
onto Xen primitives via the XAPI XML-RPC interface surfaced by
`codecraftai-interop-xen`.

The venue covers Pool/Host, Network (PIF/VIF/Bridge), Storage Repository (SR;
LVM-iSCSI, NFS, EXT, ZFS), VM (clone from template), VDI, and the XCP-ng
firewall via DotsHost or out-of-band rules (most clusters do not run a
software firewall — the provisioner records SG intent in tags and warns).
Xen has no native object storage or load balancer — `validate`-errors.  HPC
interconnect not supported.  Shared FS attach-existing only.

Every method on `XcpngCloudProvisioner` accepts `aspects: Aspects`.

---

## Requirements

### Requirement 1: Validate a Spec

#### Acceptance Criteria

1. WHEN `validate(spec, aspects)` is called THE SYSTEM SHALL ensure every VM
   has a resolvable target Pool, Host (or pool-master delegation), and SR.
2. WHEN the spec contains `CloudObjectBucket`, `CloudLoadBalancer`,
   `CloudInterconnect != NONE`, or unsupported shared-FS THE SYSTEM SHALL
   report errors.
3. WHEN the requested image is neither a Template ref nor an importable XVA
   THE SYSTEM SHALL fail naming the lookup attempted.

---

### Requirement 2: Plan

#### Acceptance Criteria

1. WHEN `plan(spec, aspects)` is called THE SYSTEM SHALL list VMs and Networks
   whose `other_config["codecraftai-run-id"]` matches and emit `PlanAction`s.
2. WHEN VM CPU/RAM drifts THE SYSTEM SHALL emit `UPDATE` honouring XenServer's
   memory ballooning when applicable.

---

### Requirement 3: Apply Idempotently

#### Acceptance Criteria

1. WHEN `apply(spec, aspects)` is called THE SYSTEM SHALL execute Network →
   SR verification → VM clone-from-template → VDI attach → cloud-init via
   xenstore `vm-data/cloud-init` → VM start.
2. WHEN re-applying THE SYSTEM SHALL make no mutating calls when every action
   is SKIP.
3. WHEN a VM carries `vpn_join` THE SYSTEM SHALL render the cloud-init
   snippet from [vpn-join-spec](../vpn-join-spec/design.md) into the
   xenstore-delivered user-data.
4. WHEN any DELETE is planned and `aspects.confirm` is false THE SYSTEM SHALL
   raise `ConfirmationRequiredError`.

---

### Requirement 4: Destroy

#### Acceptance Criteria

1. WHEN `destroy(spec, aspects)` is called with confirm THE SYSTEM SHALL
   shutdown then destroy VMs (with associated VDIs) and remove created
   Networks.
2. WHEN VPN-joined VMs are destroyed THE SYSTEM SHALL invoke
   `IVPNControlPlane.delete_device`.

---

### Requirement 5: Inventory

#### Acceptance Criteria

1. WHEN `inventory(spec, aspects)` is called THE SYSTEM SHALL enumerate
   run-id-tagged VMs across the Pool and emit `ProvisionedResource` records
   using XenTools guest-IP reporting.

---

### Requirement 6: Tag Round-Trip Fidelity

#### Acceptance Criteria

1. WHEN translating neutral tags THE SYSTEM SHALL store them under
   `VM.other_config` and the `tags` field, encoding each `key=value` pair as
   a single `tags` entry.
2. WHEN reading back THE SYSTEM SHALL recover the neutral list such that
   round-tripping is the identity.

---

### Requirement 7: Aspects on Every Call

#### Acceptance Criteria

1. WHEN any provisioner method is invoked THE SYSTEM SHALL accept and propagate
   `Aspects`.
2. WHEN omitted THE SYSTEM SHALL substitute the default `Aspects()`.
