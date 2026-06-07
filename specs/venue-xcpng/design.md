# Design — XCP-ng / XenServer Provisioner

## Overview

`XcpngCloudProvisioner` realises the neutral resource model on XCP-ng (and
Citrix Hypervisor) Pools through `codecraftai-interop-xen`, which wraps the XAPI
XML-RPC interface (`/RPC2`).  The Pool is the apex container; the
pool-master receives all writes and replicates state across hosts.

XCP-ng does not natively model tags as first-class queryable indices; the
provisioner uses `VM.other_config["codecraftai-run-id"]` plus the legacy `tags`
field to encode neutral tags.

See Also:
- [cloud-resource-model](../cloud-resource-model/design.md)
- [cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md)
- [vpn-join-spec](../vpn-join-spec/design.md)
- `codecraftai-interop-xen/Agents.md`

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    ProvisioningEngine                        │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              XcpngCloudProvisioner                           │
│  provisioning/venues/xcpng/xcpngcloudprovisioner.py          │
└────┬───────────────────┬────────────────────┬───────────────┘
     │                   │                    │
     ▼                   ▼                    ▼
┌─────────────┐  ┌──────────────────┐  ┌──────────────────────┐
│XenResolver  │  │XenTagTranslator  │  │XenCloudInitRenderer  │
│tmpl/sr/net  │  │ neutral↔other_cf │  │ xenstore vm-data     │
└─────────────┘  └──────────────────┘  └──────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│        XenClient (codecraftai-interop-xen)                      │
│   session / VM / VDI / SR / Network / VIF / pool             │
│   XAPI XML-RPC against https://<master>/RPC2                 │
└──────────────────────────────────────────────────────────────┘
```

XAPI call paths used by `apply`:

- `session.login_with_password`
- `VM.get_by_name_label` / `VM.clone` from template ref
- `VM.set_VCPUs_max` / `set_memory_*` / `set_other_config`
- `VIF.create` linking VM to Network
- `VDI.create` / `VBD.create` for additional disks
- `VM.add_to_xenstore_data` `vm-data/cloud-init/user-data` (base64)
- `VM.start`

---

## Mapping Table

| Neutral model | XCP-ng primitive | Notes |
| --- | --- | --- |
| `apod` envelope | Pool | configured per run (pool-master URL). |
| `CloudNetwork` | Network (bridged or NIC-bonded) | created or reused by name_label. |
| `CloudSubnet` | (folded; DHCP/static via cloud-init) | recorded in other_config. |
| `CloudSecurityGroup` | (no native) | recorded in tags; warn at validate. |
| `CloudKeyPair` | seed via cloud-init user-data | no first-class resource. |
| `CloudImage` | VM Template ref | resolved by name/tag. |
| `CloudInstance` | VM clone | `size` → vCPUs/memory; SR per `pick_sr`. |
| `CloudInterconnect` | unsupported | `validate`-error. |
| `CloudStorageVolume` | VDI on chosen SR. |
| `CloudObjectBucket` | unsupported | `validate`-error. |
| `CloudLoadBalancer` | unsupported | `validate`-error. |
| `CloudDnsRecord` | external | warn today. |
| `CloudSharedFilesystem(*, existing_id)` | SR mount (NFS) | attach-only. |
| `VPNJoinSpec` | xenstore `vm-data/cloud-init/user-data` base64. |
| Tags | `VM.other_config["codecraftai-run-id"]` + `tags` list. |

---

## Module Layout

```
source/packages/ccai/provisioning/venues/xcpng/
├── __init__.py
├── xcpngcloudprovisioner.py
├── xenresolver.py
├── xentagtranslator.py
├── xencloudinitrenderer.py
├── xenplanbuilder.py
├── xenapplystages.py
├── xendestroystages.py
├── xeninventory.py
└── xenerrors.py
```

---

## Idempotency

VM lookups use `VM.get_by_name_label` returning the deterministic
`<spec-name>-<run-id-short>` name; existing VMs with matching
`other_config["codecraftai-run-id"]` are SKIP candidates.  Memory and vCPU
changes use the live `set_*` calls when the VM supports dynamic reconfigure;
otherwise UPDATE-by-recreate gated on `aspects.confirm`.

---

## Testing Strategy

- `MockXenSession` returns deterministic XML-RPC responses.
- Property tests: idempotent apply, inverse destroy, tag round-trip identity.
- Validate-table tests confirm rejections.
- Live runs gated by `RUN_LIVE_XCPNG=1` against a homelab pool.
