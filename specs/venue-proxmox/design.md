# Design — Proxmox VE Provisioner

## Overview

`ProxmoxCloudProvisioner` realises the neutral resource model on Proxmox VE
through `automojo-interop-proxmox`, which wraps the Proxmox REST API (port
8006, ticket-auth + CSRF token) on `RestClientBase`.  Proxmox's apex container
is the **cluster**; resources live on **nodes** within the cluster.  The
provisioner treats one cluster as one venue instance and uses the
`automojo-run-id` Proxmox tag as the per-run discriminator.

See Also:
- [cloud-resource-model](../cloud-resource-model/design.md)
- [cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md)
- [vpn-join-spec](../vpn-join-spec/design.md)
- `automojo-interop-proxmox/Agents.md`

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    ProvisioningEngine                        │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              ProxmoxCloudProvisioner                         │
│  provisioning/venues/proxmox/proxmoxcloudprovisioner.py      │
└────┬───────────────────┬────────────────────┬───────────────┘
     │                   │                    │
     ▼                   ▼                    ▼
┌─────────────┐  ┌──────────────────┐  ┌──────────────────────┐
│PveResolver  │  │PveTagTranslator  │  │PveCloudInitRenderer  │
│tmpl/storage │  │ neutral↔string list│  │ snippet upload      │
└─────────────┘  └──────────────────┘  └──────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│        ProxmoxClient (automojo-interop-proxmox)              │
│   cluster/nodes/qemu/lxc/storage/firewall/sdn  REST          │
│   RestClientBase against https://<pve>:8006/api2/json        │
└──────────────────────────────────────────────────────────────┘
```

REST call paths used by `apply`:

- `GET/POST /cluster/sdn/vnets` (SDN VNet) or `nodes/{node}/network` (bridge)
- `GET/POST /cluster/firewall/rules`
- `GET /nodes/{node}/storage/{store}/content` (template lookup)
- `POST /nodes/{node}/qemu/{tmpl}/clone` (full or linked clone)
- `POST /nodes/{node}/qemu/{vmid}/config` for `cicustom`, `ipconfig0`, tags
- `POST /nodes/{node}/qemu/{vmid}/status/start`
- `POST /nodes/{node}/lxc` for container clones
- Snippet upload via `POST /nodes/{node}/storage/{snip}/upload` (PUT cicustom
  user-data file).

---

## Mapping Table

| Neutral model | Proxmox primitive | Notes |
| --- | --- | --- |
| `apod` envelope | Cluster | configured per run. |
| `CloudNetwork` | SDN VNet or Linux bridge | choice per cluster config. |
| `CloudSubnet` | SDN Subnet | VLAN tag honoured. |
| `CloudSecurityGroup` | Cluster firewall rules + per-VM enable | rule sets keyed by SG name. |
| `CloudKeyPair` | injected into cloud-init `ssh-authorized-keys` | no first-class resource. |
| `CloudImage` | VM template (VMID) or downloadable cloud-image | template-first. |
| `CloudInstance` | QEMU VM clone | `size` → CPU/RAM/disk via PveResolver. |
| `CloudInstance(kind=lxc)` (extension) | LXC container clone | optional v1.5. |
| `CloudInterconnect` | unsupported | `validate`-error. |
| `CloudStorageVolume` | virtual disk on storage pool | pool resolved via PveResolver. |
| `CloudObjectBucket` | unsupported | `validate`-error. |
| `CloudLoadBalancer` | unsupported | `validate`-error. |
| `CloudDnsRecord` | external | warn today. |
| `CloudSharedFilesystem(*, existing_id)` | NFS/CIFS storage mount | attach-only. |
| `VPNJoinSpec` | `cicustom` user-data snippet (uploaded) | identical pattern. |
| Tags | semicolon-delimited string list | round-trip identity. |

---

## Module Layout

```
source/packages/automojo/provisioning/venues/proxmox/
├── __init__.py
├── proxmoxcloudprovisioner.py
├── pveresolver.py
├── pvetagtranslator.py
├── pvecloudinitrenderer.py
├── pveplanbuilder.py
├── pveapplystages.py
├── pvedestroystages.py
├── pveinventory.py
└── pveerrors.py
```

---

## Idempotency

Reads filter VM/LXC listings by the `tags` field containing `automojo-run-id=<id>`.
Cloud-init snippets are content-addressed by hash; re-uploading an identical
snippet is skipped.  VM resize (CPU/RAM) uses `qemu/{vmid}/config` in-place when
the VM is stopped or hot-plug is enabled; disk resize uses `resize`.

---

## Testing Strategy

- `MockProxmoxClient` returns deterministic JSON, including ticket+CSRF auth
  handshake.
- Property tests: idempotent apply, inverse destroy, tag round-trip identity.
- Validate-table tests confirm rejections (object bucket, LB, interconnect,
  unsupported shared-FS).
- Snippet upload deduped by SHA256.
- Live runs gated by `RUN_LIVE_PVE=1` against a homelab cluster.
