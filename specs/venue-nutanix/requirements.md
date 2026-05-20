# Requirements — Nutanix AHV Provisioner

## Introduction

The `venue-nutanix` feature provides `automojo-provisioning` with the ability to
stand up VMs on Nutanix AHV clusters via Prism Central.  It implements the
`CloudProvisioner` lifecycle defined in
[cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md) and maps the
neutral resource model in [cloud-resource-model](../cloud-resource-model/design.md)
onto Nutanix primitives via the Prism Central v3/v4 REST APIs surfaced by
`automojo-interop-nutanix` (built on `automojo-restclient-base`).

The venue covers VPC (Flow Networking), Subnet, Security Policy (Flow), VM,
Volume, and Image.  Nutanix does not natively offer public object storage in
Prism; `CloudObjectBucket` maps to **Objects** (the Nutanix object-storage
product) when configured as an extension, otherwise it is a `validate`-error.
HPC interconnect not supported.  Shared FS attach-existing only (Nutanix Files
share mount).

Every method on `NutanixCloudProvisioner` accepts `aspects: Aspects`.

---

## Requirements

### Requirement 1: Validate a Spec

#### Acceptance Criteria

1. WHEN `validate(spec, aspects)` is called THE SYSTEM SHALL ensure every VM
   has a resolvable target Cluster UUID and Image.
2. WHEN `CloudObjectBucket` is requested and Nutanix Objects is not configured
   in the spec's `apod` THE SYSTEM SHALL report an error.
3. WHEN the spec contains `CloudLoadBalancer`, `CloudInterconnect != NONE`, or
   unsupported shared-FS kinds THE SYSTEM SHALL report errors.

---

### Requirement 2: Plan

#### Acceptance Criteria

1. WHEN `plan(spec, aspects)` is called THE SYSTEM SHALL list resources by the
   `automojo-run-id` category on VMs and Subnets and emit `PlanAction`s.
2. WHEN VM hardware drifts THE SYSTEM SHALL emit `UPDATE` honouring AHV's
   hot-plug rules where possible.

---

### Requirement 3: Apply Idempotently

#### Acceptance Criteria

1. WHEN `apply(spec, aspects)` is called THE SYSTEM SHALL execute VPC/Subnet
   → Security Policy → Image verification → VM create → disk attach →
   cloud-init via VM `guest_customization.cloud_init.user_data` → power-on.
2. WHEN re-applying THE SYSTEM SHALL make no mutating calls when every action
   is SKIP.
3. WHEN a VM carries `vpn_join` THE SYSTEM SHALL render the cloud-init snippet
   from [vpn-join-spec](../vpn-join-spec/design.md) into the VM's
   `guest_customization.cloud_init.user_data` (base64-encoded).
4. WHEN any DELETE is planned and `aspects.confirm` is false THE SYSTEM SHALL
   raise `ConfirmationRequiredError`.
5. WHEN any Prism task is dispatched THE SYSTEM SHALL await it via the task
   poll loop with `aspects.timeout_seconds`.

---

### Requirement 4: Destroy

#### Acceptance Criteria

1. WHEN `destroy(spec, aspects)` is called with confirm THE SYSTEM SHALL
   power-off then delete VMs, delete Subnets, and delete VPCs created by the
   run.
2. WHEN VPN-joined VMs are deleted THE SYSTEM SHALL invoke
   `IVPNControlPlane.delete_device`.

---

### Requirement 5: Inventory

#### Acceptance Criteria

1. WHEN `inventory(spec, aspects)` is called THE SYSTEM SHALL enumerate
   run-id-categoried VMs and emit `ProvisionedResource` records using NGT
   guest-IP reporting.

---

### Requirement 6: Tag (Category) Round-Trip Fidelity

#### Acceptance Criteria

1. WHEN translating neutral tags to Nutanix Categories+Values THE SYSTEM SHALL
   ensure a Category exists per neutral key and a Value exists per
   `key=value` pair.
2. WHEN reading Categories back THE SYSTEM SHALL recover the neutral form so
   round-tripping is the identity.

---

### Requirement 7: Aspects on Every Call

#### Acceptance Criteria

1. WHEN any provisioner method is invoked THE SYSTEM SHALL accept and propagate
   `Aspects`.
2. WHEN omitted THE SYSTEM SHALL substitute the default `Aspects()`.
