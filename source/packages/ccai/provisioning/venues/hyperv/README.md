# Hyper-V Provisioning Venue

`HypervCloudProvisioner` realises the neutral cloud-resource model on
Microsoft Hyper-V hosts.  Hyper-V exposes no REST API in the OS; the venue
drives the `Hyper-V` PowerShell module through the
[`codecraftai-interop-hyperv`](../../../../../../../codecraftai-interop-hyperv)
`HypervClient`, which runs cmdlets over WinRM via an `ICommandRunner`.

## Lifecycle

The venue implements the five-verb `CloudProvisioner` lifecycle —
`validate / plan / apply / destroy / inventory` — described in
[cloud-provisioner-lifecycle](../../../../../../specs/cloud-provisioner-lifecycle/design.md).

* **validate** — shape + semantic checks, no remote I/O.  Rejects
  unsupported kinds (see mapping table).
* **plan** — read-only `Get-VMSwitch` / `Get-VM` / `Get-VHD`; emits
  CREATE / SKIP / UPDATE actions.  VM hardware drift surfaces as UPDATE.
* **apply** — VMSwitch ensure → parent VHD verification → differencing
  boot VHDX → `New-VM` → processor/memory sizing → data VHDX attach →
  network adapter → `Set-VM -Notes` → cloud-init ISO mount → `Start-VM`.
  Idempotent: `apply ∘ apply` makes no further mutating calls.
* **destroy** — `Stop-VM -Force` → `Remove-VM` → VHDX deletion →
  `Remove-VMSwitch` for run-owned switches, then VPN device cleanup.
* **inventory** — enumerates run-id-owned VMs using KVP-reported IPs.

## Mapping Table

| Neutral model         | Hyper-V primitive                              |
| --------------------- | ---------------------------------------------- |
| `CloudNetwork`        | VMSwitch (External when a host adapter is set, otherwise Internal) |
| `CloudSubnet`         | folded; DHCP/static handled via cloud-init     |
| `CloudSecurityGroup`  | no native surface — warn at validate           |
| `CloudKeyPair`        | seeded into cloud-init `ssh_authorized_keys`   |
| `CloudImage`          | parent VHD/VHDX path resolved by `HvResolver`  |
| `CloudInstance`       | VM (Gen2) via `New-VM` + differencing boot VHDX |
| `CloudStorageVolume`  | additional VHDX + `Add-VMHardDiskDrive`        |
| `CloudInterconnect`   | HPC kinds unsupported — `validate`-error       |
| `CloudObjectBucket`   | unsupported — `validate`-error                 |
| `CloudLoadBalancer`   | unsupported — `validate`-error                 |
| `CloudDnsRecord`      | external — warn at validate                    |
| `CloudSharedFilesystem` | attach-only SMB share (`VENUE_NATIVE`)       |
| `VPNJoinSpec`         | cloud-init in a NoCloud ISO (Linux) or `SetupComplete.cmd` (Windows) |
| Tags + run-id         | JSON envelope under the `ccai` key in `VM.Notes` |

## VPN Join

A VM carrying `vpn_join` has the cloud-init snippet from
[vpn-join-spec](../../../../../../specs/vpn-join-spec/design.md) rendered by
the shared M6 `vpncloudinitrenderer` and folded into the NoCloud
`user-data` (Linux) or a PowerShell unattend script in `SetupComplete.cmd`
(Windows).  Destroy de-registers VPN devices through the injected
`IVPNControlPlane`.

## Live runs

Integration runs are gated by `RUN_LIVE_HYPERV=1` against a homelab
Hyper-V host; the unit suite uses an in-memory `MockHypervClient`.
