# Requirements — Hyper-V Provisioner

## Introduction

The `venue-hyperv` feature provides `codecraftai-provisioning` with the ability to
stand up VMs on Microsoft Hyper-V hosts (standalone or in a Failover Cluster).
It implements the `CloudProvisioner` lifecycle defined in
[cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md) and maps the
neutral resource model in [cloud-resource-model](../cloud-resource-model/design.md)
onto Hyper-V primitives.  Hyper-V exposes no REST API in the box; the
`codecraftai-interop-hyperv` package wraps **PowerShell over WinRM** through an
`ICommandRunner`, invoking the `Hyper-V` PowerShell module
(`New-VM`, `New-VMSwitch`, `Set-VMNetworkAdapter`, etc.).

The venue covers VMSwitch (External / Internal / Private), Virtual Machine,
Virtual Hard Disk (VHD/VHDX), and (for Linux guests) cloud-init via the
Hyper-V Data Exchange (KVP) service or attached config-drive ISO.  Hyper-V
has no native object storage or LB — `validate`-errors.  HPC interconnect not
supported.  Shared FS attach-existing only (SMB share).

Every method on `HypervCloudProvisioner` accepts `aspects: Aspects`.

---

## Requirements

### Requirement 1: Validate a Spec

#### Acceptance Criteria

1. WHEN `validate(spec, aspects)` is called THE SYSTEM SHALL ensure every VM
   has a resolvable target Host and VHD storage path.
2. WHEN the spec contains `CloudObjectBucket`, `CloudLoadBalancer`,
   `CloudInterconnect != NONE`, or unsupported shared-FS kinds THE SYSTEM
   SHALL report errors.
3. WHEN the requested image is neither a parent VHD/VHDX nor a downloadable
   ISO with auto-install THE SYSTEM SHALL fail naming the lookup attempted.

---

### Requirement 2: Plan

#### Acceptance Criteria

1. WHEN `plan(spec, aspects)` is called THE SYSTEM SHALL list VMs and Switches
   on the host whose notes / KVP-pool entries carry the `codecraftai-run-id`
   marker and emit `PlanAction`s.
2. WHEN VM hardware drifts THE SYSTEM SHALL emit `UPDATE` via
   `Set-VM` / `Set-VMProcessor` / `Set-VMMemory`.

---

### Requirement 3: Apply Idempotently

#### Acceptance Criteria

1. WHEN `apply(spec, aspects)` is called THE SYSTEM SHALL execute VMSwitch
   ensure → parent VHD verification → differencing VHDX creation → `New-VM`
   → `Set-VMNetworkAdapter` → cloud-init delivery (config-drive ISO mount or
   KVP injection) → `Start-VM`.
2. WHEN re-applying THE SYSTEM SHALL make no mutating calls when every action
   is SKIP.
3. WHEN a VM carries `vpn_join` THE SYSTEM SHALL render the cloud-init
   snippet from [vpn-join-spec](../vpn-join-spec/design.md) into the
   config-drive `user-data` (Linux) or as a PowerShell unattend script in
   `SetupComplete.cmd` (Windows).
4. WHEN any DELETE is planned and `aspects.confirm` is false THE SYSTEM SHALL
   raise `ConfirmationRequiredError`.

---

### Requirement 4: Destroy

#### Acceptance Criteria

1. WHEN `destroy(spec, aspects)` is called with confirm THE SYSTEM SHALL
   `Stop-VM -Force` then `Remove-VM` (with VHD deletion) and `Remove-VMSwitch`
   for run-id-owned switches.
2. WHEN VPN-joined VMs are removed THE SYSTEM SHALL invoke
   `IVPNControlPlane.delete_device`.

---

### Requirement 5: Inventory

#### Acceptance Criteria

1. WHEN `inventory(spec, aspects)` is called THE SYSTEM SHALL enumerate
   run-id-tagged VMs and emit `ProvisionedResource` records using Integration
   Services / KVP-reported IP addresses.

---

### Requirement 6: Run-ID Marker Encoding

#### Acceptance Criteria

1. WHEN translating neutral tags THE SYSTEM SHALL store them in `VM.Notes` as a
   JSON object under the key `ccai`.
2. WHEN reading `VM.Notes` back THE SYSTEM SHALL parse the JSON and recover
   the neutral tag list such that round-tripping is the identity.

---

### Requirement 7: Aspects on Every Call

#### Acceptance Criteria

1. WHEN any provisioner method is invoked THE SYSTEM SHALL accept and propagate
   `Aspects`, including to the WinRM `ICommandRunner`.
2. WHEN omitted THE SYSTEM SHALL substitute the default `Aspects()`.
