# Design — GCP Cloud Provisioner

## Overview

`GcpCloudProvisioner` realises the neutral resource model on Google Cloud Platform.
The defining structural choice for GCP is the project as the apex container — all
resources are scoped to a project, and the `automojo-run-id` label is the per-run
discriminator inside it.  All Google API calls go through `automojo-interop-gcp`'s
`GcpClient`, which wraps `google-auth` plus the `google-cloud-compute`,
`google-cloud-tpu`, `google-cloud-storage`, `google-cloud-dns`, and
`google-cloud-filestore` / `google-cloud-parallelstore` SDKs.

TPUs are a distinct resource type, not a VM accelerator — the provisioner branches at
the spec-walk stage and dispatches `CloudAcceleratorSpec(kind=TPU)` instances to a
separate TPU apply path.

See Also:
- [cloud-resource-model](../cloud-resource-model/design.md)
- [cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md)
- [vpn-join-spec](../vpn-join-spec/design.md)
- [gcp-credentials](../../../automojo-credentials/specs/gcp-credentials/design.md)
- `automojo-interop-gcp/Agents.md`

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    ProvisioningEngine                        │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                  GcpCloudProvisioner                         │
│  provisioning/venues/google/googlecloudprovisioner.py        │
└────┬───────────────────┬─────────────────────┬──────────────┘
     │                   │                     │
     ▼                   ▼                     ▼
┌─────────────┐  ┌────────────────────┐  ┌──────────────────┐
│GcpResolver  │  │GcpLabelTranslator  │  │GcpUserDataRender │
│img/sku/accel│  │ neutral↔labels     │  │ metadata user-data│
└─────────────┘  └────────────────────┘  └──────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                GcpClient (automojo-interop-gcp)              │
│   compute / tpu_v2 / storage / dns / filestore / parallel    │
└──────────────────────────────────────────────────────────────┘
```

SDK call paths used by `apply`:

- `compute.networks.get` / `insert`
- `compute.subnetworks.get` / `insert`
- `compute.firewalls.get` / `insert`
- `compute.resource_policies.get` / `insert` (compact placement)
- `compute.instances.get` / `insert` with `metadata.items["user-data"]`
- `compute.disks.get` / `insert`
- `tpu_v2.NodeServiceClient.get_node` / `create_node` (TPU branch)
- `storage.Client.bucket(name).reload()` / `create()`
- `dns.ResourceRecordSetsClient.list` / `change`
- `filestore.CloudFilestoreManagerClient.get_instance`
- `parallelstore.ParallelstoreClient.get_instance`

---

## Mapping Table

| Neutral model | GCP resource | Notes |
| --- | --- | --- |
| `CloudNetwork` | VPC network (`compute.networks`) | mode forced to custom. |
| `CloudSubnet` | Subnetwork | `cidr` → `ip_cidr_range`. |
| `CloudSecurityGroup` | Firewall rules | one rule per ingress entry; source ranges from `source_cidrs`. |
| `CloudKeyPair` | Project-level SSH key in metadata | OS Login bypassed when key supplied directly. |
| `CloudImage` | Image family lookup | `ubuntu/24.04` → `projects/ubuntu-os-cloud/global/images/family/ubuntu-2404-lts`. |
| `CloudInstance` | Compute Engine Instance | `size` → `machine_type`; `vpn_join` → `metadata.items["user-data"]`. |
| `CloudInstance.accelerators` (GPU) | `guest_accelerators` + machine family | A3-Mega/Ultra for H100/H200. |
| `CloudInstance.accelerators` (TPU) | TPU Node | branched to `tpu_v2.NodeServiceClient`. |
| `CloudInterconnect(NONE→compact)` | `ResourcePolicy` (compact placement) | one policy per `interconnect_group`. |
| `CloudStorageVolume` | Persistent Disk | `type` → `pd-ssd` / `pd-balanced`. |
| `CloudObjectBucket` | GCS bucket | name globally unique; suffix from run-id. |
| `CloudLoadBalancer` | GCLB (v1.5 stub) | `validate`-errors today. |
| `CloudDnsRecord` | Cloud DNS record set | zone resolved by `zone_name`. |
| `CloudSharedFilesystem(LUSTRE)` | Parallelstore | attach-only via `existing_id`. |
| `CloudSharedFilesystem(FILESTORE)` | Filestore instance | attach via NFSv3. |
| `VPNJoinSpec` | cloud-init `runcmd` in instance metadata | identical to AWS. |
| Tags | GCP labels (lowercased, sanitised) | round-trip identity for already-conformant sets. |

---

## Module Layout

```
source/packages/automojo/provisioning/venues/google/
├── __init__.py
├── googlecloudprovisioner.py
├── gcpresolver.py
├── gcplabeltranslator.py
├── gcpuserdatarenderer.py
├── gcpplanbuilder.py
├── gcpapplystages.py
├── gcptpubranch.py            # TPU-specific apply / destroy
├── gcpdestroystages.py
├── gcpinventory.py
└── gcperrors.py
```

---

## Data Models

```python
@dataclass
class GcpApplyResult:
    run_id: str
    project: str
    created: list[ProvisionedResource]
    updated: list[ProvisionedResource]
    skipped: list[ProvisionedResource]
    failed: list[ProvisioningError]
```

---

## Idempotency

Every resource is keyed by `<spec-name>-<run-id-short>`.  Read-before-create
queries call `get(...)` and catch `NotFound` to drive CREATE.  Mutable attribute
drift drives UPDATE; tag/label changes alone drive `set_labels` patches without
recreating the resource.  TPU nodes are immutable in most attributes — drift forces
UPDATE-by-recreate gated on `aspects.confirm`.

---

## Testing Strategy

- `MockGcpClient` per service, table-driven on `(method, key) → response`.
- Property tests: idempotent apply, inverse destroy, label round-trip identity
  for inputs already conformant to GCP rules.
- TPU branch tested independently — TPU spec must never touch the Compute Engine
  apply stage and vice versa.
- Compact-placement test: N instances sharing `interconnect_group` produce one
  `ResourcePolicy` and N `instances.insert` calls referencing it.
- Live runs gated by `RUN_LIVE_GCP=1`.
