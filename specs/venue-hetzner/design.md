# Design — Hetzner Cloud Provisioner

## Overview

`HetznerCloudProvisioner` realises the neutral resource model on Hetzner Cloud
through the `hcloud` SDK surfaced by `codecraftai-interop-hetzner`.  Hetzner is a
deliberately small, cost-efficient cloud: there is no object storage in the
Cloud product (Hetzner Storage Box is a separate, FTP/SMB/SSH-style product
outside this provisioner's scope), no HPC interconnect, and a thin GPU SKU set.
The provisioner is honest about these gaps in `validate`.

See Also:
- [cloud-resource-model](../cloud-resource-model/design.md)
- [cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md)
- [vpn-join-spec](../vpn-join-spec/design.md)
- `codecraftai-interop-hetzner/Agents.md`

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    ProvisioningEngine                        │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              HetznerCloudProvisioner                         │
│  provisioning/venues/hetzner/hetznercloudprovisioner.py      │
└────┬───────────────────┬────────────────────┬───────────────┘
     │                   │                    │
     ▼                   ▼                    ▼
┌─────────────┐  ┌──────────────────┐  ┌──────────────────────┐
│HetznerResolv│  │HetznerLabelTrans │  │HetznerUserDataRender │
│img/type/loc │  │  neutral↔dict    │  │  user_data + vpn_join│
└─────────────┘  └──────────────────┘  └──────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│        HetznerClient (codecraftai-interop-hetzner)              │
│   networks / firewalls / ssh_keys / servers / volumes / dns  │
│   hcloud SDK against api.hetzner.cloud                       │
└──────────────────────────────────────────────────────────────┘
```

REST call paths used by `apply`:

- `client.networks.get_by_name` / `.create`
- `client.firewalls.get_by_name` / `.create` / `.apply_to_resources`
- `client.ssh_keys.get_by_fingerprint` / `.create`
- `client.servers.get_by_name` / `.create` with `user_data`
- `client.volumes.get_by_name` / `.create` / `.attach`
- Hetzner DNS API: `GET/POST /api/v1/records`.

---

## Mapping Table

| Neutral model | Hetzner resource | Notes |
| --- | --- | --- |
| `CloudNetwork` | Network | `cidr` → `ip_range`. |
| `CloudSubnet` | Subnet on Network | `cidr` → `ip_range`. |
| `CloudSecurityGroup` | Firewall | `apply_to_resources` per Server tag. |
| `CloudKeyPair` | SSH Key | dedup by fingerprint. |
| `CloudImage` | image name | `ubuntu/24.04` → `ubuntu-24.04`. |
| `CloudInstance` | Server | `size` → server type slug (`cx22`, `cpx41`, `cax21`, `gpu-*`). |
| `CloudInstance.accelerators` | GPU server type | minimal catalog; resolver lists what Hetzner publishes. |
| `CloudInterconnect` | unsupported | `validate`-error for non-`NONE`. |
| `CloudStorageVolume` | Volume | attach-after-create; same-location only. |
| `CloudObjectBucket` | unsupported | `validate`-error. |
| `CloudLoadBalancer` | LoadBalancer (v1.5 stub) | warn today. |
| `CloudDnsRecord` | Hetzner DNS record | zone resolved by `zone_name`. |
| `CloudSharedFilesystem` | unsupported | `validate`-error. |
| `VPNJoinSpec` | cloud-init `user_data` | identical to other venues. |
| Tags | Hetzner labels dict | round-trip identity for conformant inputs. |

---

## Module Layout

```
source/packages/ccai/provisioning/venues/hetzner/
├── __init__.py
├── hetznercloudprovisioner.py
├── hetznerresolver.py
├── hetznerlabeltranslator.py
├── hetzneruserdatarenderer.py
├── hetznerplanbuilder.py
├── hetznerapplystages.py
├── hetznerdestroystages.py
├── hetznerinventory.py
└── hetznererrors.py
```

---

## Idempotency

Reads use `get_by_name` (or `get_by_fingerprint` for SSH keys).  Mutating calls
are skipped when the live object's labels match and mutable attributes are equal.
Server type changes are UPDATE-by-recreate (Hetzner supports rescaling for some
types; rescaling falls back to recreate when not).

---

## Testing Strategy

- `MockHetznerClient` returns deterministic SDK-shaped objects.
- Property tests: idempotent apply, inverse destroy, label round-trip identity
  for conformant inputs.
- Validate-table tests confirm object-storage, interconnect, and shared-FS
  rejections.
- Live runs gated by `RUN_LIVE_HETZNER=1`.
