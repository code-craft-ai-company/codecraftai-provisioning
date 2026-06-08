# Requirements — Azure Cloud Provisioner

## Introduction

The `venue-azure` feature provides `codecraftai-provisioning` with the ability to stand
up infrastructure on Microsoft Azure.  It implements the `CloudProvisioner`
lifecycle defined in
[cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md) and maps the
neutral resource model from [cloud-resource-model](../cloud-resource-model/design.md)
onto Azure primitives via the `azure-mgmt-*` SDKs surfaced by
`codecraftai-interop-azure`.  Azure adds one structural concept absent from AWS — the
`ResourceGroup` — that the provisioner treats as the apex container for an `apod`'s
resources.

The venue covers ResourceGroup, VNet, Subnet, NSG, NIC, Virtual Machine, Managed
Disk, Blob storage, and Azure DNS, plus the §7.1 GPU/RDMA extensions: it resolves
`CloudAcceleratorSpec` values to InfiniBand-capable SKUs in the NDv5 / NCv4 families,
and realises `CloudSharedFilesystem(kind=LUSTRE)` as Azure Managed Lustre, with
Azure NetApp Files (ANF) as an alternative for `kind=AZUREFILES`.

Each method on `AzureCloudProvisioner` accepts an `aspects: Aspects` argument so the
caller controls timeouts, retries, persistence, and confirmation.  All Azure SDK
calls are delegated to `codecraftai-interop-azure`; the venue holds no SDK clients
directly.

---

## Requirements

### Requirement 1: Validate a Spec

**User Story:** As a coordinator, I want every Azure spec validated against
Azure-specific constraints before any apply, so that capacity, region, and SKU
mistakes fail fast.

#### Acceptance Criteria

1. WHEN `validate(spec, aspects)` is called THE SYSTEM SHALL ensure every resource is
   anchored to a `ResourceGroup` name resolved from the `apod` block.
2. WHEN the spec contains `CloudInterconnect(kind=EFA)` or `kind=OCI_RDMA` THE SYSTEM
   SHALL report an error stating that Azure exposes only InfiniBand via NDv5/NCv4.
3. WHEN the spec contains `CloudSharedFilesystem(kind=WEKA)` THE SYSTEM SHALL report
   an error pointing at the Azure Managed Lustre / ANF substitutions.
4. WHEN an instance requests an accelerator that resolves to an InfiniBand SKU and
   no proximity placement group is named THE SYSTEM SHALL emit a warning and create
   one automatically.

---

### Requirement 2: Plan a Spec

**User Story:** As a coordinator, I want a read-before-create diff against the live
subscription so I know what `apply` will do.

#### Acceptance Criteria

1. WHEN `plan(spec, aspects)` is called THE SYSTEM SHALL query the
   `ResourceGroup` and every contained resource by `codecraftai-run-id` tag.
2. WHEN a resource is absent THE SYSTEM SHALL emit `PlanAction(kind=CREATE)`.
3. WHEN a resource matches THE SYSTEM SHALL emit `PlanAction(kind=SKIP)`.
4. WHEN tag drift, NSG rule drift, or VM size drift is detected THE SYSTEM SHALL
   emit `PlanAction(kind=UPDATE)`.

---

### Requirement 3: Apply a Plan Idempotently

**User Story:** As a coordinator, I want apply to be re-runnable so a half-finished
run can be resumed.

#### Acceptance Criteria

1. WHEN `apply(spec, aspects)` is called THE SYSTEM SHALL ensure the ResourceGroup
   first, then execute network → NSG → NIC → VM → managed disk → blob → DNS.
2. WHEN re-applying a spec whose every action is SKIP THE SYSTEM SHALL make no
   mutating SDK calls.
3. WHEN an instance carries `vpn_join` THE SYSTEM SHALL render the cloud-init
   snippet from [vpn-join-spec](../vpn-join-spec/design.md) and pass it through the
   VM `os_profile.custom_data` (base64-encoded) for Linux or as a Custom Script
   Extension for Windows.
4. WHEN `aspects.confirm` is `False` and any DELETE is planned THE SYSTEM SHALL
   raise `ConfirmationRequiredError`.

---

### Requirement 4: Destroy in Reverse Order

**User Story:** As a coordinator, I want destroy to tear down only this run's
resources.

#### Acceptance Criteria

1. WHEN `destroy(spec, aspects)` is called with `confirm=True` THE SYSTEM SHALL
   delete VMs → NICs → disks → NSGs → subnets → VNets → ResourceGroup (only when
   empty and owned by the run-id).
2. WHEN the ResourceGroup contains resources not tagged with the run-id THE SYSTEM
   SHALL leave the ResourceGroup intact.
3. WHEN each VM carrying `vpn_join` is terminated THE SYSTEM SHALL invoke
   `IVPNControlPlane.delete_device` for its overlay device.

---

### Requirement 5: Inventory

**User Story:** As a coordinator, I want a uniform inventory listing for
landscape emission.

#### Acceptance Criteria

1. WHEN `inventory(spec, aspects)` is called THE SYSTEM SHALL enumerate all
   run-id-tagged resources in the ResourceGroup and return `ProvisionedResource`
   records.

---

### Requirement 6: InfiniBand SKU Resolution (NDv5 / NCv4)

**User Story:** As a coordinator, I want neutral accelerators to resolve to
IB-capable Azure VM SKUs.

#### Acceptance Criteria

1. WHEN `CloudInterconnect(kind=INFINIBAND_NDR)` is requested THE SYSTEM SHALL
   resolve to a SKU in the NDv5 family (`Standard_ND96isr_H100_v5` family) or the
   NCv4 family for H100 NVL configurations.
2. WHEN the SKU is realised THE SYSTEM SHALL place the VM into a Proximity
   Placement Group shared by all VMs in the same `interconnect_group`.
3. WHEN the requested accelerator has no IB-capable Azure SKU THE SYSTEM SHALL fail
   in `validate`.

---

### Requirement 7: Azure Managed Lustre / ANF Shared FS

**User Story:** As a coordinator, I want `CloudSharedFilesystem` to map to Azure
Managed Lustre or ANF, depending on `kind`.

#### Acceptance Criteria

1. WHEN `CloudSharedFilesystem(kind=LUSTRE, existing_id=...)` is supplied THE
   SYSTEM SHALL look up the Managed Lustre file system and add fstab mounts via
   cloud-init.
2. WHEN `kind=AZUREFILES` is supplied with `existing_id` THE SYSTEM SHALL mount the
   ANF volume via NFSv4.1.
3. WHEN `existing_id` is absent THE SYSTEM SHALL fail with the "provision path not
   supported in v1" error per §7.6.

---

### Requirement 8: Tag Round-Trip Fidelity

**User Story:** As a coordinator, I want neutral tags to survive translation
through Azure `tags` dicts.

#### Acceptance Criteria

1. WHEN translating neutral tags to Azure THE SYSTEM SHALL flatten the
   `List[Dict[str,str]]` into a single `Dict[str,str]` and verify no key collisions
   occur.
2. WHEN a collision is detected THE SYSTEM SHALL fail in `validate`.
3. WHEN reading Azure tags back THE SYSTEM SHALL reconstruct the neutral form so
   that round-tripping is the identity for any collision-free tag set.

---

### Requirement 9: Aspects on Every Call

**User Story:** As a coordinator, I want behaviour parameters to flow through every
call.

#### Acceptance Criteria

1. WHEN any provisioner method is invoked THE SYSTEM SHALL accept an `Aspects`
   parameter and forward it to the Azure interop layer.
2. WHEN `aspects` is omitted THE SYSTEM SHALL substitute the default `Aspects()`.
