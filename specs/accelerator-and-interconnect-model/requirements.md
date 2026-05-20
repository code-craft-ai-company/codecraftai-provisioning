# Requirements

## Introduction

GPU / TPU / IPU / ASIC workloads cannot be described by `(cpu, ram, disk)` alone.
The accelerator and interconnect model adds the additional shape required to specify
"give me 8× H100 SXM with NVLink and 3.2 Tbps InfiniBand" in a venue-neutral form,
plus the **shared filesystems** that almost always accompany those workloads.

This spec adds four classes:

- `CloudAcceleratorSpec` — node-internal accelerator description
- `CloudInterconnect` — inter-node fabric description
- `CloudSharedFilesystem` — WEKA / Lustre / VAST / GPFS / venue-native
- `SharedFsMountSpec` — the mount instruction attached to an instance

…and extends `CloudInstance` with the optional fields that wire them in.  The fields
are additive: a non-accelerated instance leaves them `None` and behaves identically
to the §2.7 baseline model.  Per the §7.6 plan decision, all enums ship complete on
day one even though only some venues implement each value in v1.

---

## Requirements

### Requirement 1: CloudAcceleratorSpec

**User Story:** As a provisioning author for an AI workload, I want to describe my
GPU need in a single venue-neutral object.

#### Acceptance Criteria

1. THE SYSTEM SHALL expose `CloudAcceleratorSpec(kind, model: str, count: int,
   interconnect, memory_gb: int)` as a `SchemaObject`.
2. THE SYSTEM SHALL define `kind` as `Literal["GPU", "TPU", "IPU", "ASIC"]`.
3. THE SYSTEM SHALL define `interconnect` (node-internal) as
   `Literal["NONE", "PCIE", "NVLINK", "NVSWITCH", "INFINITY_FABRIC"]`.
4. WHEN `count <= 0` THE SYSTEM SHALL raise `SchemaValidationError`.
5. WHEN `model` is not in the accelerator catalog THE SYSTEM SHALL raise
   `SchemaSemanticError` during lifecycle `validate`.
6. THE SYSTEM SHALL accept any catalog-resident neutral model name regardless of
   whether the resolved venue supports it; venue support is checked during validate.

---

### Requirement 2: CloudInterconnect

**User Story:** As a provisioning author, I want to describe inter-node fabric so the
provisioner places instances in a placement group / cluster network that supports it.

#### Acceptance Criteria

1. THE SYSTEM SHALL expose `CloudInterconnect(kind, bandwidth_gbps: int, topology)`.
2. THE SYSTEM SHALL define `kind` as `Literal["ETHERNET", "ROCE",
   "INFINIBAND_HDR", "INFINIBAND_NDR", "INFINIBAND_XDR", "EFA", "OCI_RDMA"]`.
3. THE SYSTEM SHALL define `topology` as `Literal["NONE", "RAIL_OPTIMIZED",
   "FAT_TREE", "DRAGONFLY"]`.
4. WHEN `bandwidth_gbps <= 0` THE SYSTEM SHALL raise `SchemaValidationError`.
5. WHERE the resolved venue does not support the requested `kind` THE SYSTEM SHALL
   raise `SchemaSemanticError` during lifecycle `validate`.

---

### Requirement 3: CloudSharedFilesystem

**User Story:** As a provisioning author, I want to declare shared high-bandwidth
filesystems separately from per-instance volumes.

#### Acceptance Criteria

1. THE SYSTEM SHALL expose `CloudSharedFilesystem(name, kind, size_tb: Optional[int],
   throughput_gbps: Optional[int], mount_targets: List[SharedFsMountSpec],
   existing_id: Optional[str], tags)`.
2. THE SYSTEM SHALL define `kind` as `Literal["WEKA", "LUSTRE", "VAST", "GPFS",
   "EFS", "FILESTORE", "AZUREFILES", "BEEGFS", "VENUE_NATIVE"]`.
3. WHEN `existing_id` is set THE SYSTEM SHALL operate in attach-only mode.
4. WHEN `existing_id` is `None` and `size_tb` is also `None` THE SYSTEM SHALL raise
   `SchemaValidationError` (must be either attach or full provision).
5. WHERE a venue does not yet support provisioning shared FS (v1 default) and
   `existing_id is None` THE SYSTEM SHALL raise `NotImplementedError` with a
   pointer to the tracking issue (per §7.6 decision).

---

### Requirement 4: SharedFsMountSpec

**User Story:** As a provisioning author, I want to declare per-instance mount points
for shared filesystems.

#### Acceptance Criteria

1. THE SYSTEM SHALL expose `SharedFsMountSpec(filesystem_name: str,
   target_instance: str, mount_path: str, mount_options: List[str])`.
2. WHEN `mount_path` is empty or does not start with `/` THE SYSTEM SHALL raise
   `SchemaValidationError`.
3. WHEN `filesystem_name` does not resolve to a declared `CloudSharedFilesystem` in
   the spec THE SYSTEM SHALL raise `SchemaSemanticError` during validate.

---

### Requirement 5: CloudInstance Extensions

**User Story:** As a provisioning author, I want my accelerator/interconnect/shared-FS
declarations to attach to an instance without breaking baseline instances.

#### Acceptance Criteria

1. THE SYSTEM SHALL add optional fields to `CloudInstance`: `accelerators`,
   `interconnect`, `placement_group`, `shared_fs_mounts`.
2. WHEN none of the optional fields are set THE SYSTEM SHALL preserve the §2.7
   baseline shape and the instance SHALL pass through every venue provisioner
   exactly as before.
3. WHEN `interconnect` is set and `placement_group` is `None` THE SYSTEM SHALL log a
   warning that placement may be best-effort.
4. WHEN any `shared_fs_mount.target_instance` does not match `CloudInstance.name`
   THE SYSTEM SHALL raise `SchemaSemanticError` during validate.

---

### Requirement 6: Connectivity Boundary

**User Story:** As a framework author, I want the spec to refuse configurations where
overlay-VPN traffic is mistakenly used for training-fabric paths.

#### Acceptance Criteria

1. WHEN a `CloudInstance` has both `vpn_join` and `interconnect.kind` is in the
   training-fabric set (`INFINIBAND_*`, `EFA`, `OCI_RDMA`) THE SYSTEM SHALL accept
   the configuration but warn that VPN covers control-plane only (per §7.4).
2. THE SYSTEM SHALL NOT silently route shared-filesystem traffic through any VPN
   overlay; venue provisioners SHALL pin shared-FS mounts to the native VPC plane.
