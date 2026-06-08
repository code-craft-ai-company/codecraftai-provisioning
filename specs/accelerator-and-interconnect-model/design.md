# Design

## Overview

This spec adds the accelerator, interconnect, and shared-filesystem vocabulary needed
to provision HPC / AI workloads through the same neutral pipeline that handles
generic IaaS.  All additions are *additive* to the §2.7 baseline model — a CPU-only
instance never touches any of these classes.

The plan's §7 decisions drive three structural choices baked into this design:

1. The accelerator **catalog** (which neutral names exist, which venues support them,
   what SKUs they map to) lives in a YAML file loaded by the
   [`accelerator-catalog`](../accelerator-catalog/design.md) module — not in any class
   here.  These classes only reference catalog entries by neutral name.
2. The interconnect enum carries every value (Ethernet through XDR InfiniBand) on
   day one; venue support is checked at validate-time, not at class-construction time.
3. Shared filesystems support **attach-only in v1, provision-and-attach in v1.5** —
   the class shape accepts both, but the lifecycle layer raises `NotImplementedError`
   on the provision path for v1 venues.

---

## Architecture

```
        ┌─────────────────────────────┐
        │      CloudInstance          │
        │   (accelerators / interconnect / shared_fs_mounts)
        └──────┬───────────────┬──────┘
               │               │
               ▼               ▼
   CloudAcceleratorSpec    CloudInterconnect
       │                       │
       │  references           │  venue-checked
       ▼                       ▼
   accelerator-catalog    venue support matrix
   (YAML data file)       (per-venue resolver)

   CloudSharedFilesystem
       │
       │ mount_targets[]
       ▼
   SharedFsMountSpec  ──► CloudInstance.shared_fs_mounts
```

---

## Data Model

```python
class CloudAcceleratorSpec(SchemaObject):
    kind: Literal["GPU", "TPU", "IPU", "ASIC"]
    model: str                                    # neutral name; resolved via catalog
    count: int
    interconnect: Literal["NONE", "PCIE", "NVLINK", "NVSWITCH", "INFINITY_FABRIC"]
    memory_gb: int


class CloudInterconnect(SchemaObject):
    kind: Literal[
        "ETHERNET",
        "ROCE",
        "INFINIBAND_HDR",
        "INFINIBAND_NDR",
        "INFINIBAND_XDR",
        "EFA",
        "OCI_RDMA",
    ]
    bandwidth_gbps: int
    topology: Literal["NONE", "RAIL_OPTIMIZED", "FAT_TREE", "DRAGONFLY"]


class SharedFsMountSpec(SchemaObject):
    filesystem_name: str          # references CloudSharedFilesystem.name
    target_instance: str          # references CloudInstance.name
    mount_path: str               # absolute path
    mount_options: List[str]


class CloudSharedFilesystem(SchemaObject):
    name: str
    kind: Literal["WEKA", "LUSTRE", "VAST", "GPFS", "EFS",
                  "FILESTORE", "AZUREFILES", "BEEGFS", "VENUE_NATIVE"]
    size_tb: Optional[int]               # None when existing_id is set
    throughput_gbps: Optional[int]
    mount_targets: List[SharedFsMountSpec]
    existing_id: Optional[str]           # set => attach-only mode
    tags: List[Dict[str, str]]
```

Optional fields added to `CloudInstance` (see
[cloud-resource-model](../cloud-resource-model/design.md)):

```python
accelerators:      Optional[List[CloudAcceleratorSpec]] = None
interconnect:      Optional[CloudInterconnect]          = None
placement_group:   Optional[str]                        = None
shared_fs_mounts:  Optional[List[SharedFsMountSpec]]    = None
```

---

## Module Layout

```
source/packages/ccai/provisioning/model/cloud/
├── cloudacceleratorspec.py
├── cloudinterconnect.py
├── cloudsharedfilesystem.py
└── sharedfsmountspec.py
```

`CloudInstance` lives in `cloudinstance.py` and gains the four optional fields above;
no new file is created for the extension.

---

## Venue Support Matrix (Validate-Time)

The matrix is data, not code — it lives alongside the accelerator catalog and is
consulted by `provisioner.validate(...)`.  Sketch:

| Venue          | INFINIBAND_NDR | EFA | OCI_RDMA | LUSTRE provision | LUSTRE attach |
| -------------- | -------------- | --- | -------- | ---------------- | ------------- |
| aws            | no             | yes | no       | no (v1.5)        | yes (FSx)     |
| azure          | yes            | no  | no       | no (v1.5)        | yes (AMLFS)   |
| gcp            | no             | no  | no       | no (v1.5)        | yes           |
| oracle         | no             | no  | yes      | no (v1.5)        | yes           |
| crusoe         | yes            | no  | no       | no               | yes           |
| coreweave      | yes            | no  | no       | no               | yes (VAST/WEKA)|
| vsphere        | no             | no  | no       | no               | partial       |

The matrix is **published** by the venue plugins via `venue_capabilities()` so adding a
venue updates the matrix without editing this spec.

---

## See Also

- [accelerator-catalog](../accelerator-catalog/design.md) — neutral-name → venue-SKU table.
- [cloud-resource-model](../cloud-resource-model/design.md) — base `CloudInstance`.
- [cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md) — runs the
  venue-support matrix at validate-time.
- [vpn-join-spec](../vpn-join-spec/design.md) — control-plane VPN is independent of
  training fabric.
- [workload-venue-model](../workload-venue-model/design.md) — `WorkloadCluster` node
  pools also carry these fields.

---

## Testing Strategy

- **Unit tests** — `to_dict / from_dict` round-trip per class; rejection cases for
  `count <= 0`, `bandwidth_gbps <= 0`, empty `mount_path`, missing `size_tb` with no
  `existing_id`.
- **Cross-class tests** — `SharedFsMountSpec.target_instance` references resolve
  during validate; `CloudInstance` with no optional field passes through unchanged.
- **Venue-support tests** — a stub venue with empty capability matrix rejects every
  accelerator request with `SchemaSemanticError`.
- **Connectivity boundary test** — combination of `vpn_join` plus training-fabric
  `interconnect.kind` succeeds but emits the documented warning.
- Property tests for the catalog round-trip live in the accelerator-catalog spec, not
  here; this spec only verifies that catalog membership is **looked up** correctly.
