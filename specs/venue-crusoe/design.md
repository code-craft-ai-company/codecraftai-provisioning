# Design — Crusoe Cloud Provisioner

## Overview

`CrusoeCloudProvisioner` realises the neutral resource model on Crusoe Cloud.
Crusoe's product shape is AWS-adjacent: VPC, Subnet, Firewall Rules,
Instance, Disk, IB Partition for HPC interconnect, and a managed file storage
option.  All calls go through `codecraftai-interop-crusoe`'s `CrusoeClient`,
which wraps the REST API on `RestClientBase` against
`https://api.crusoecloud.com/v1alpha5/`.

See Also:
- [cloud-resource-model](../cloud-resource-model/design.md)
- [cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md)
- [vpn-join-spec](../vpn-join-spec/design.md)
- `codecraftai-interop-crusoe/Agents.md`

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    ProvisioningEngine                        │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              CrusoeCloudProvisioner                          │
│  provisioning/venues/crusoe/crusoecloudprovisioner.py        │
└────┬───────────────────┬────────────────────┬───────────────┘
     │                   │                    │
     ▼                   ▼                    ▼
┌─────────────┐  ┌──────────────────┐  ┌──────────────────────┐
│CrusoeResolv │  │CrusoeLabelTrans  │  │CrusoeUserDataRender  │
│type/loc/ib  │  │ neutral↔dict     │  │ user_data + vpn_join │
└─────────────┘  └──────────────────┘  └──────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│        CrusoeClient (codecraftai-interop-crusoe)                │
│   vpcs / subnets / firewall-rules / ssh-keys / instances /   │
│   disks / ib-partitions / file-systems  REST                 │
└──────────────────────────────────────────────────────────────┘
```

REST call paths used by `apply`:

- `GET /projects/{pid}/vpcs` / `POST`
- `GET /projects/{pid}/subnets` / `POST`
- `GET /projects/{pid}/firewall-rules` / `POST`
- `GET /projects/{pid}/ssh-keys` / `POST`
- `GET /projects/{pid}/ib-partitions` / `POST`
- `GET /projects/{pid}/instances` / `POST` with `user_data` and
  `ib_partition_id`
- `GET /projects/{pid}/disks` / `POST` / `PATCH attach`
- `GET /projects/{pid}/storage-disks` (file-system attach)

---

## Mapping Table

| Neutral model | Crusoe primitive | Notes |
| --- | --- | --- |
| `apod` envelope | Project | configured per run. |
| `CloudNetwork` | VPC | `cidr` → `cidr_block`. |
| `CloudSubnet` | Subnet | `zone` → location. |
| `CloudSecurityGroup` | Firewall Rule(s) | one rule per ingress entry. |
| `CloudKeyPair` | SSH Key | dedup by fingerprint. |
| `CloudImage` | image alias | resolver maps family/version. |
| `CloudInstance` | Instance | `size`/`accelerators` → `instance_type`. |
| `CloudInterconnect(INFINIBAND_*)` | IB Partition + `ib_partition_id` | grouped by `interconnect_group`. |
| `CloudStorageVolume` | Disk | attach-after-create. |
| `CloudObjectBucket` / `CloudLoadBalancer` | unsupported | `validate`-error. |
| `CloudDnsRecord` | external | warn today. |
| `CloudSharedFilesystem(VENUE_NATIVE, existing_id)` | storage-disk file-system attach | attach-only. |
| `VPNJoinSpec` | `user_data` in launch | identical pattern. |
| Tags | Crusoe labels dict | round-trip identity. |

---

## Module Layout

```
source/packages/ccai/provisioning/venues/crusoe/
├── __init__.py
├── crusoecloudprovisioner.py
├── crusoeresolver.py
├── crusoelabeltranslator.py
├── crusoeuserdatarenderer.py
├── crusoeplanbuilder.py
├── crusoeapplystages.py
├── crusoeibpartition.py        # IB partition ensure-and-attach helper
├── crusoedestroystages.py
├── crusoeinventory.py
└── crusoeerrors.py
```

---

## Idempotency

Reads filter by label `codecraftai-run-id=<id>`.  IB partitions are checked by
name before create.  instance_type changes are UPDATE-by-recreate gated on
`aspects.confirm`.

---

## Testing Strategy

- `MockCrusoeClient` returns deterministic paged JSON.
- Property tests: idempotent apply, inverse destroy, label round-trip
  identity, IB partition grouping.
- Validate-table tests confirm rejections.
- Live runs gated by `RUN_LIVE_CRUSOE=1` (GPU per-second charges).
