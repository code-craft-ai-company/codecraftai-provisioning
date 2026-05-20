# Design — Linode (Akamai Cloud) Provisioner

## Overview

`LinodeCloudProvisioner` realises the neutral resource model on Linode via the
`linode_api4` SDK surfaced by `automojo-interop-linode`.  Linode is a mid-tier
cloud with VPC + Cloud Firewall + Block Storage + Object Storage + DNS, plus a
small GPU SKU set.  There is no HPC interconnect and no native shared-FS service
of the WEKA/Lustre class.

See Also:
- [cloud-resource-model](../cloud-resource-model/design.md)
- [cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md)
- [vpn-join-spec](../vpn-join-spec/design.md)
- `automojo-interop-linode/Agents.md`

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    ProvisioningEngine                        │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              LinodeCloudProvisioner                          │
│  provisioning/venues/linode/linodecloudprovisioner.py        │
└────┬──────────────────┬───────────────────┬─────────────────┘
     │                  │                   │
     ▼                  ▼                   ▼
┌─────────────┐  ┌────────────────┐  ┌──────────────────────┐
│LinodeResolv │  │LinodeTagTrans  │  │LinodeUserDataRender  │
│type/img/reg │  │ k=v string list│  │ metadata.user_data   │
└─────────────┘  └────────────────┘  └──────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│        LinodeClient (automojo-interop-linode)                │
│   vpcs / firewalls / instances / volumes / object-storage    │
│   linode_api4 SDK against api.linode.com                     │
└──────────────────────────────────────────────────────────────┘
```

REST call paths used by `apply`:

- `client.vpcs()` / `client.vpc_create(...)`
- `client.networking.firewalls()` / `firewall_create(...)`
- `client.linode.instances()` / `instance_create(...)` with `metadata.user_data`
- `client.volumes()` / `volume_create(...)` / `volume.attach(linode)`
- `client.object_storage.buckets()` / `bucket_create(...)`
- `client.domains()` / `domain.record_create(...)`

---

## Mapping Table

| Neutral model | Linode resource | Notes |
| --- | --- | --- |
| `CloudNetwork` | VPC | per-region. |
| `CloudSubnet` | VPC Subnet | `cidr` → `ipv4`. |
| `CloudSecurityGroup` | Cloud Firewall | rules per direction. |
| `CloudKeyPair` | SSH key on Instance create | included in `authorized_keys`. |
| `CloudImage` | image id | `ubuntu/24.04` → `linode/ubuntu24.04`. |
| `CloudInstance` | Linode (Instance) | `size` → type slug (`g6-standard-4`, `g1-gpu-rtx6000-1`). |
| `CloudInstance.accelerators` | GPU type slug | minimal catalog. |
| `CloudInterconnect` | unsupported | `validate`-error for non-`NONE`. |
| `CloudStorageVolume` | Block Storage Volume | same-region only. |
| `CloudObjectBucket` | Object Storage bucket | cluster-scoped. |
| `CloudLoadBalancer` | NodeBalancer (v1.5 stub) | warn today. |
| `CloudDnsRecord` | Domain record | zone resolved by name. |
| `CloudSharedFilesystem` | unsupported | `validate`-error. |
| `VPNJoinSpec` | `metadata.user_data` | rendered as cloud-init when image supports. |
| Tags | string list `["k=v", ...]` | round-trip identity. |

---

## Module Layout

```
source/packages/automojo/provisioning/venues/linode/
├── __init__.py
├── linodecloudprovisioner.py
├── linoderesolver.py
├── linodetagtranslator.py
├── linodeuserdatarenderer.py
├── linodeplanbuilder.py
├── linodeapplystages.py
├── linodedestroystages.py
├── linodeinventory.py
└── linodeerrors.py
```

---

## Idempotency

Reads are tag-filtered listings.  Instances support `linode.resize(...)` for some
type changes; the provisioner uses it when both source and target types support
resize, otherwise UPDATE-by-recreate gated on `aspects.confirm`.

---

## Testing Strategy

- `MockLinodeClient` returns deterministic SDK objects.
- Property tests: idempotent apply, inverse destroy, tag round-trip identity.
- Validate-table tests confirm interconnect and shared-FS rejections.
- Live runs gated by `RUN_LIVE_LINODE=1`.
