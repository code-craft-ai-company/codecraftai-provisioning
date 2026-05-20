# Design — Vultr Cloud Provisioner

## Overview

`VultrCloudProvisioner` realises the neutral resource model on Vultr.  Vultr's
API is REST-only (no first-party SDK), so the interop layer builds on
`automojo-restclient-base`.  The provisioner is mid-feature: VPC + Firewall +
Block Storage + Object Storage + DNS + a thin GPU SKU set; no HPC interconnect;
no managed shared FS of the WEKA/Lustre class.

See Also:
- [cloud-resource-model](../cloud-resource-model/design.md)
- [cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md)
- [vpn-join-spec](../vpn-join-spec/design.md)
- `automojo-interop-vultr/Agents.md`

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    ProvisioningEngine                        │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              VultrCloudProvisioner                           │
│  provisioning/venues/vultr/vultrcloudprovisioner.py          │
└────┬──────────────────┬───────────────────┬─────────────────┘
     │                  │                   │
     ▼                  ▼                   ▼
┌─────────────┐  ┌────────────────┐  ┌──────────────────────┐
│VultrResolver│  │VultrTagTrans   │  │VultrUserDataRenderer │
│plan/os/reg  │  │ k=v string list│  │ user_data + vpn_join │
└─────────────┘  └────────────────┘  └──────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│        VultrClient (automojo-interop-vultr)                  │
│   vpc2 / firewalls / ssh-keys / instances / blocks / object  │
│   RestClientBase against api.vultr.com/v2                    │
└──────────────────────────────────────────────────────────────┘
```

REST call paths used by `apply`:

- `GET /vpc2` / `POST /vpc2`
- `GET /firewalls` / `POST /firewalls` + `/firewalls/{id}/rules`
- `GET /ssh-keys` / `POST /ssh-keys`
- `GET /instances` / `POST /instances` with `user_data` (base64)
- `GET /blocks` / `POST /blocks` / `POST /blocks/{id}/attach`
- `GET /object-storage` / `POST /object-storage`
- `GET /domains/{name}/records` / `POST`

---

## Mapping Table

| Neutral model | Vultr resource | Notes |
| --- | --- | --- |
| `CloudNetwork` | VPC 2.0 | `cidr` → `v4_subnet` + `v4_subnet_mask`. |
| `CloudSubnet` | (folded into VPC 2.0) | recorded in tags. |
| `CloudSecurityGroup` | Firewall Group + rules | one group per neutral SG. |
| `CloudKeyPair` | SSH Key | dedup by name+key. |
| `CloudImage` | OS id (`os_id`) | `ubuntu/24.04` → resolved via `GET /os`. |
| `CloudInstance` | Instance | `size` → plan id (`vc2-2c-4gb`, `vhf-*`, `vcg-*`). |
| `CloudInstance.accelerators` | GPU plan id | minimal catalog. |
| `CloudInterconnect` | unsupported | `validate`-error for non-`NONE`. |
| `CloudStorageVolume` | Block Storage | same-region only; attach-after-create. |
| `CloudObjectBucket` | Object Storage subscription + bucket | cluster-scoped. |
| `CloudLoadBalancer` | LB (v1.5 stub) | warn today. |
| `CloudDnsRecord` | Domain record | zone resolved by name. |
| `CloudSharedFilesystem` | unsupported | `validate`-error. |
| `VPNJoinSpec` | base64 `user_data` | identical to other venues. |
| Tags | string list `["k=v", ...]` | round-trip identity. |

---

## Module Layout

```
source/packages/automojo/provisioning/venues/vultr/
├── __init__.py
├── vultrcloudprovisioner.py
├── vultrresolver.py
├── vultrtagtranslator.py
├── vultruserdatarenderer.py
├── vultrplanbuilder.py
├── vultrapplystages.py
├── vultrdestroystages.py
├── vultrinventory.py
└── vultrerrors.py
```

---

## Idempotency

Reads use paged listings filtered by the `tag` query parameter.  Plan changes
are UPDATE-by-recreate (Vultr resize across plan families is unreliable across
SKUs).

---

## Testing Strategy

- `MockVultrClient` returns deterministic paged JSON.
- Property tests: idempotent apply, inverse destroy, tag round-trip identity.
- Validate-table tests confirm interconnect / shared-FS rejections.
- Live runs gated by `RUN_LIVE_VULTR=1`.
