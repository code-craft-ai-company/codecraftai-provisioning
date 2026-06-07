# Design — Nebius Provisioner

## Overview

`NebiusCloudProvisioner` realises the neutral resource model on Nebius.  The
product shape is GPU-cloud-typical: VPC, Subnet, SG, Instance, Disk, GPU
Cluster (IB-enabled placement), managed file storage, managed object storage.
All API calls go through `codecraftai-interop-nebius`'s `NebiusClient` on
`RestClientBase`.

Nebius's structural choice is the **parent_id** — every resource is anchored
to a folder/project parent; the provisioner treats the apex parent as the
venue instance identifier.

See Also:
- [cloud-resource-model](../cloud-resource-model/design.md)
- [cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md)
- [vpn-join-spec](../vpn-join-spec/design.md)
- `codecraftai-interop-nebius/Agents.md`

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    ProvisioningEngine                        │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              NebiusCloudProvisioner                          │
│  provisioning/venues/nebius/nebiuscloudprovisioner.py        │
└────┬───────────────────┬────────────────────┬───────────────┘
     │                   │                    │
     ▼                   ▼                    ▼
┌─────────────┐  ┌──────────────────┐  ┌──────────────────────┐
│NebiusResolv │  │NebiusLabelTrans  │  │NebiusUserDataRender  │
│preset/img   │  │ neutral↔dict     │  │ metadata user-data   │
└─────────────┘  └──────────────────┘  └──────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│        NebiusClient (codecraftai-interop-nebius)                │
│   vpc / subnet / sg / ssh / gpu-cluster / instance /         │
│   disk / file-storage / object-storage  REST                 │
└──────────────────────────────────────────────────────────────┘
```

REST call paths used by `apply`:

- `GET/POST /v1/vpcs` and `subnets`
- `GET/POST /v1/security-groups`
- `GET/POST /v1/ssh-keys`
- `GET/POST /v1/gpu-clusters`
- `GET/POST /v1/instances` with `metadata.user-data`
- `GET/POST /v1/disks` / `POST .../attach`
- `GET/POST /v1/file-storages` (attach by id)
- `GET/POST /v1/buckets`

---

## Mapping Table

| Neutral model | Nebius primitive | Notes |
| --- | --- | --- |
| `apod` envelope | parent_id (project/folder) | configured per run. |
| `CloudNetwork` | VPC | `cidr` → `ipv4_cidr_block`. |
| `CloudSubnet` | Subnet | `zone` → AZ. |
| `CloudSecurityGroup` | Security Group | rule sets. |
| `CloudKeyPair` | SSH Key | dedup by fingerprint. |
| `CloudImage` | image id | resolver maps family/version. |
| `CloudInstance` | Instance | `size`/`accelerators` → preset slug. |
| `CloudInterconnect(INFINIBAND_*)` | GPU Cluster | grouped by `interconnect_group`. |
| `CloudStorageVolume` | Disk | attach-after-create. |
| `CloudObjectBucket` | Object Storage Bucket | parent-scoped. |
| `CloudLoadBalancer` | unsupported in v1 | `validate`-error. |
| `CloudDnsRecord` | DNS (when configured) | optional v1.5. |
| `CloudSharedFilesystem(VENUE_NATIVE, existing_id)` | File Storage attach | attach-only. |
| `VPNJoinSpec` | `metadata["user-data"]` | identical pattern. |
| Tags | Nebius labels dict | round-trip identity. |

---

## Module Layout

```
source/packages/ccai/provisioning/venues/nebius/
├── __init__.py
├── nebiuscloudprovisioner.py
├── nebiusresolver.py
├── nebiuslabeltranslator.py
├── nebiususerdatarenderer.py
├── nebiusplanbuilder.py
├── nebiusapplystages.py
├── nebiusgpucluster.py         # ensure-and-attach for IB grouping
├── nebiusdestroystages.py
├── nebiusinventory.py
└── nebiuserrors.py
```

---

## Idempotency

Reads filter by `labels.codecraftai-run-id`.  GPU Cluster lookups by name
precede create.  Preset (instance type) changes are UPDATE-by-recreate gated
on `aspects.confirm`.

---

## Testing Strategy

- `MockNebiusClient` returns deterministic JSON.
- Property tests: idempotent apply, inverse destroy, label round-trip
  identity, GPU Cluster grouping.
- Validate-table tests confirm LB and shared-FS-provision rejections.
- Live runs gated by `RUN_LIVE_NEBIUS=1`.
