# Design — DigitalOcean Cloud Provisioner

## Overview

`DigitalOceanCloudProvisioner` realises the neutral resource model on
DigitalOcean.  DigitalOcean is intentionally lower-feature than the hyperscalers:
no native HPC interconnect, no first-class shared FS of the WEKA/Lustre class, and
a thin GPU SKU catalog.  The provisioner is therefore honest in `validate` about
which neutral asks have no DO realisation and errors cleanly for them.

All API calls go through `automojo-interop-digitalocean`'s `DigitalOceanClient`,
which wraps the `pydo` SDK against `api.digitalocean.com/v2/`.

See Also:
- [cloud-resource-model](../cloud-resource-model/design.md)
- [cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md)
- [vpn-join-spec](../vpn-join-spec/design.md)
- `automojo-interop-digitalocean/Agents.md`

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    ProvisioningEngine                        │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              DigitalOceanCloudProvisioner                    │
│  provisioning/venues/digitalocean/digitaloceancloud...py     │
└────┬──────────────────┬───────────────────┬─────────────────┘
     │                  │                   │
     ▼                  ▼                   ▼
┌─────────────┐  ┌────────────────┐  ┌──────────────────────┐
│DoResolver   │  │DoTagTranslator │  │DoUserDataRenderer    │
│size/img/reg │  │ k=v string list│  │ user_data + vpn_join │
└─────────────┘  └────────────────┘  └──────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│        DigitalOceanClient (automojo-interop-digitalocean)    │
│   vpcs / firewalls / droplets / volumes / spaces / dns       │
│   pydo SDK against api.digitalocean.com/v2                   │
└──────────────────────────────────────────────────────────────┘
```

REST call paths used by `apply`:

- `GET /v2/vpcs` (paged) → read-before-create
- `POST /v2/vpcs`
- `GET /v2/firewalls?tag_name=<run-id>`
- `POST /v2/firewalls`
- `GET /v2/account/keys` → SSH key reuse
- `POST /v2/account/keys`
- `GET /v2/droplets?tag_name=<run-id>`
- `POST /v2/droplets` with `user_data`
- `GET /v2/volumes` / `POST /v2/volumes` / `POST /v2/volumes/.../attach`
- Spaces: S3-compatible `HEAD /bucket` / `PUT /bucket` via the Spaces endpoint.
- `GET /v2/domains/{name}/records` / `POST`.

---

## Mapping Table

| Neutral model | DigitalOcean resource | Notes |
| --- | --- | --- |
| `CloudNetwork` | VPC | per-region; default region VPC reused unless `name` set. |
| `CloudSubnet` | (folded into VPC) | DO has no separate subnet object; provisioner stores subnet metadata in tags only. |
| `CloudSecurityGroup` | Cloud Firewall | rules per direction; `droplet_ids` attached at apply. |
| `CloudKeyPair` | SSH Key (account-scoped) | uploaded by fingerprint; reused. |
| `CloudImage` | image slug | `ubuntu/24.04` → `ubuntu-24-04-x64`. |
| `CloudInstance` | Droplet | `size` → DO size slug; `vpn_join` → `user_data`. |
| `CloudInstance.accelerators` | GPU Droplet | `H100×8` → `gpu-h100x8`. |
| `CloudInterconnect` | unsupported | `validate`-error for non-`NONE`. |
| `CloudStorageVolume` | Block Storage volume | attach-after-create. |
| `CloudObjectBucket` | Spaces bucket | S3-compatible; region-scoped. |
| `CloudLoadBalancer` | DO Load Balancer (v1.5 stub) | warn today. |
| `CloudDnsRecord` | DNS record | domain must exist; created by name. |
| `CloudSharedFilesystem(LUSTRE/WEKA/...)` | unsupported | `validate`-error. |
| `VPNJoinSpec` | cloud-init in `user_data` | identical to other venues. |
| Tags | string list `["k=v", ...]` | round-trip identity required. |

---

## Module Layout

```
source/packages/automojo/provisioning/venues/digitalocean/
├── __init__.py
├── digitaloceancloudprovisioner.py
├── doresolver.py
├── dotagtranslator.py
├── douserdatarenderer.py
├── doplanbuilder.py
├── doapplystages.py
├── dodestroystages.py
├── doinventory.py
└── doerrors.py
```

---

## Idempotency

Read-before-create uses `tag_name=<run-id>` queries.  SSH keys are deduped by
fingerprint.  Droplet size changes are UPDATE-by-recreate (DO does not support
in-place resize for all sizes); gated on `aspects.confirm`.

---

## Testing Strategy

- `MockDigitalOceanClient` returns deterministic paged JSON.
- Property tests: idempotent apply, inverse destroy, tag round-trip identity
  for arbitrary `key=value` pairs (with `=` escaping).
- Validate-table tests confirm shared-FS and interconnect asks fail loudly.
- Live runs gated by `RUN_LIVE_DO=1`.
