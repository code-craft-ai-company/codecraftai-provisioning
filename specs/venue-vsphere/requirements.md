# Requirements — VSphere Provisioner

## Introduction

The `venue-vsphere` feature provides `automojo-provisioning` with the ability to
stand up VMs on a VMware vSphere/vCenter environment.  It implements the
`CloudProvisioner` lifecycle defined in
[cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md) and maps the
neutral resource model in [cloud-resource-model](../cloud-resource-model/design.md)
onto vSphere primitives via the **rebuilt** `VSphereClient` in
`automojo-interop-vsphere` (see PLAN §6.1–§6.2 and IMPLEMENTATION-PLAN §1.15).

The venue covers Distributed Virtual Switch/Port Group, Content Library template
clone or `VmCreateSpec` build, datastore selection, virtual disk attachment, and
guest customisation (cloud-init for Linux, sysprep for Windows).  Several
neutral asks have no faithful vSphere realisation and **must fail loudly** rather
than silently: `CloudObjectBucket` has no equivalent; `CloudLoadBalancer`
requires NSX (and `automojo-interop-nsx` is a separate package per PLAN §6.6),
so it is a `validate`-error when NSX is absent; `CloudInterconnect(kind != NONE)`
is a `validate`-error (HPC fabrics are out of vSphere's scope here); shared FS
of WEKA/Lustre class is `validate`-error or attach-existing only via NFS
datastores.

Every method on `VSphereCloudProvisioner` accepts `aspects: Aspects`; every
async vCenter task is awaited through `TaskHandle.wait(aspects=...)`.

---

## Requirements

### Requirement 1: Validate a Spec

#### Acceptance Criteria

1. WHEN `validate(spec, aspects)` is called THE SYSTEM SHALL ensure every VM has
   a resolvable datacenter, cluster, and folder path.
2. WHEN the spec contains `CloudObjectBucket` THE SYSTEM SHALL report an error
   stating vSphere has no native object-storage primitive.
3. WHEN the spec contains `CloudLoadBalancer` and NSX is not configured THE
   SYSTEM SHALL report an error pointing to `automojo-interop-nsx`.
4. WHEN the spec contains `CloudInterconnect(kind != NONE)` or
   `CloudSharedFilesystem(kind in {LUSTRE,WEKA,VAST,GPFS})` without
   `existing_id` (NFS datastore mount) THE SYSTEM SHALL report an error.
5. WHEN the requested image is neither a Content Library item nor a VM template
   in the configured folder THE SYSTEM SHALL fail naming the lookup attempted.

---

### Requirement 2: Plan

#### Acceptance Criteria

1. WHEN `plan(spec, aspects)` is called THE SYSTEM SHALL list resources by the
   `automojo-run-id` vSphere category tag and emit `PlanAction`s.
2. WHEN a VM's hardware (CPU/RAM/disk) drifts THE SYSTEM SHALL emit `UPDATE`
   where vSphere supports in-place reconfigure, otherwise UPDATE-by-recreate.
3. WHEN port-group VLAN drifts THE SYSTEM SHALL emit `UPDATE`.

---

### Requirement 3: Apply Idempotently

#### Acceptance Criteria

1. WHEN `apply(spec, aspects)` is called THE SYSTEM SHALL execute DVS / Port
   Group → Content Library lookup → VM clone-from-library OR create-from-spec
   → disk attach → guest customisation → power-on.
2. WHEN re-applying THE SYSTEM SHALL make no mutating calls when every action
   is SKIP.
3. WHEN a VM carries `vpn_join` THE SYSTEM SHALL render the cloud-init snippet
   from [vpn-join-spec](../vpn-join-spec/design.md) into the guest
   customisation `cloud_init.user_data`.
4. WHEN any DELETE is planned and `aspects.confirm` is false THE SYSTEM SHALL
   raise `ConfirmationRequiredError`.
5. WHEN any vCenter task is dispatched THE SYSTEM SHALL await it via
   `TaskHandle.wait(aspects=aspects)`.

---

### Requirement 4: Destroy

#### Acceptance Criteria

1. WHEN `destroy(spec, aspects)` is called with confirm THE SYSTEM SHALL
   power-off, then delete VMs, then delete port groups created by the run.
2. WHEN VPN-joined VMs are deleted THE SYSTEM SHALL invoke
   `IVPNControlPlane.delete_device`.

---

### Requirement 5: Inventory

#### Acceptance Criteria

1. WHEN `inventory(spec, aspects)` is called THE SYSTEM SHALL enumerate VMs and
   port groups tagged with the run-id and emit `ProvisionedResource` records
   with the IPs vCenter has observed.

---

### Requirement 6: Content Library Template Resolution

#### Acceptance Criteria

1. WHEN a `CloudImage` is realised THE SYSTEM SHALL first look up a Content
   Library item by tag matching `family + version`.
2. WHEN no library item matches THE SYSTEM SHALL fall back to a folder-scoped
   VM template lookup; missing in both is a `validate`-error.

---

### Requirement 7: Datastore Selection

#### Acceptance Criteria

1. WHEN a `CloudStorageVolume` is realised and no explicit datastore is
   supplied THE SYSTEM SHALL call
   `VSphereClient.find_datastore_with_free_gb(...)` and pick the least-loaded
   datastore meeting the size requirement.
2. WHEN no datastore meets the requirement THE SYSTEM SHALL fail with a
   capacity error.

---

### Requirement 8: Tag Round-Trip Fidelity

#### Acceptance Criteria

1. WHEN translating neutral tags to vSphere categories+tags THE SYSTEM SHALL
   create one category per neutral key and one tag per `key=value` pair,
   preserving the value verbatim.
2. WHEN reading vSphere tags back THE SYSTEM SHALL reconstruct the neutral form
   so round-tripping is the identity for any input.

---

### Requirement 9: Aspects on Every Call

#### Acceptance Criteria

1. WHEN any provisioner method is invoked THE SYSTEM SHALL accept and propagate
   `Aspects`, including to `TaskHandle.wait`.
2. WHEN omitted THE SYSTEM SHALL substitute the default `Aspects()`.
