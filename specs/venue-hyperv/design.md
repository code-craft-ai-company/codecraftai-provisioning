# Design — Hyper-V Provisioner

## Overview

`HypervCloudProvisioner` realises the neutral resource model on Microsoft
Hyper-V hosts.  Hyper-V offers no REST API in the OS — control is via the
`Hyper-V` PowerShell module, executed remotely over WinRM through an
`ICommandRunner`.  The `automojo-interop-hyperv` package owns the PowerShell
command construction and result parsing (every cmdlet is invoked with
`ConvertTo-Json -Compress` for deterministic stdout).

Hyper-V has no first-class tagging system; the provisioner uses `VM.Notes` to
store a JSON envelope `{"automojo": {"run_id": ..., "tags": [...]}}`.

See Also:
- [cloud-resource-model](../cloud-resource-model/design.md)
- [cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md)
- [vpn-join-spec](../vpn-join-spec/design.md)
- `automojo-interop-hyperv/Agents.md`

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    ProvisioningEngine                        │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              HypervCloudProvisioner                          │
│  provisioning/venues/hyperv/hypervcloudprovisioner.py        │
└────┬───────────────────┬────────────────────┬───────────────┘
     │                   │                    │
     ▼                   ▼                    ▼
┌─────────────┐  ┌──────────────────┐  ┌──────────────────────┐
│HvResolver   │  │HvNotesTrans      │  │HvCloudInitRenderer   │
│vhd/switch   │  │ JSON in VM.Notes │  │ ISO + KVP delivery   │
└─────────────┘  └──────────────────┘  └──────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│        HyperVClient (automojo-interop-hyperv)                │
│   Get-VM / New-VM / New-VMSwitch / Set-VMNetworkAdapter /    │
│   New-VHD / Add-VMHardDiskDrive / Start-VM ...               │
│   PowerShell over WinRM via ICommandRunner                   │
└──────────────────────────────────────────────────────────────┘
```

Command paths used by `apply` (all `| ConvertTo-Json -Compress`):

- `Get-VMSwitch -Name <n>` / `New-VMSwitch -Name <n> -SwitchType External
  -NetAdapterName <n>`
- `Get-VHD -Path <p>` (parent verification)
- `New-VHD -Path <p> -ParentPath <pp> -Differencing`
- `Get-VM -Name <n>` / `New-VM -Name <n> -Path <p> -VHDPath <p>
  -SwitchName <n> -MemoryStartupBytes <b>`
- `Set-VMProcessor` / `Set-VMMemory` / `Set-VMNetworkAdapter`
- `Set-VM -Notes <json>` for tag encoding
- `Add-VMDvdDrive` to mount the config-drive ISO
- `Start-VM`

---

## Mapping Table

| Neutral model | Hyper-V primitive | Notes |
| --- | --- | --- |
| `apod` envelope | Host or Failover Cluster | configured per run. |
| `CloudNetwork` | VMSwitch (External/Internal/Private) | reused by name. |
| `CloudSubnet` | (folded; DHCP/static via cloud-init) | recorded in notes. |
| `CloudSecurityGroup` | (no native) | recorded in notes; honest warning at validate. |
| `CloudKeyPair` | seeded via cloud-init user-data. |
| `CloudImage` | parent VHD/VHDX path | resolver maps family/version. |
| `CloudInstance` | VM (Gen2 by default) | `size` → CPU/RAM/disk. |
| `CloudInterconnect` | unsupported | `validate`-error. |
| `CloudStorageVolume` | additional VHDX + `Add-VMHardDiskDrive`. |
| `CloudObjectBucket` | unsupported | `validate`-error. |
| `CloudLoadBalancer` | unsupported | `validate`-error. |
| `CloudDnsRecord` | external | warn today. |
| `CloudSharedFilesystem(*, existing_id)` | SMB share mount in guest | attach-only. |
| `VPNJoinSpec` | cloud-init in config-drive ISO (Linux) or `SetupComplete.cmd` (Windows). |
| Tags | JSON object in `VM.Notes`. |

---

## Module Layout

```
source/packages/automojo/provisioning/venues/hyperv/
├── __init__.py
├── hypervcloudprovisioner.py
├── hvresolver.py
├── hvnotestranslator.py
├── hvcloudinitrenderer.py
├── hvplanbuilder.py
├── hvapplystages.py
├── hvdestroystages.py
├── hvinventory.py
└── hverrors.py
```

---

## Idempotency

VM lookups use `Get-VM -Name` returning a JSON record; reading the `Notes`
field reveals whether the VM is owned by the current run-id.  Reconfigure uses
in-place cmdlets for non-disruptive properties; disruptive changes are
UPDATE-by-recreate gated on `aspects.confirm`.

---

## Testing Strategy

- `MockCommandRunner` returns deterministic JSON outputs matching the
  PowerShell cmdlets used.
- Property tests: idempotent apply, inverse destroy, notes-JSON tag
  round-trip identity.
- Validate-table tests confirm rejections.
- Cloud-init ISO content-hash determinism tested independently.
- Live runs gated by `RUN_LIVE_HYPERV=1` against a homelab Hyper-V host.
