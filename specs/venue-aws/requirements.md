# Requirements — AWS Cloud Provisioner

## Introduction

The `venue-aws` feature provides `automojo-provisioning` with the ability to stand up,
reconcile, and tear down infrastructure on Amazon Web Services.  It implements the
`CloudProvisioner` lifecycle defined in
[cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md)
(`validate / plan / apply / destroy / inventory`) and maps the neutral resource model in
[cloud-resource-model](../cloud-resource-model/design.md) onto AWS-native primitives.
A maintenance coordinator owns the spec; this venue only knows how to translate the
neutral spec to `boto3` calls and back, idempotently, with full read-before-create
semantics.

The venue covers the v1 resource families: VPC, Subnet, Internet Gateway, Route Table,
Security Group, KeyPair, AMI resolution, EC2 Instance, EBS Volume, S3 Bucket, and
Route53 record.  It additionally honours the §7.1 accelerator/interconnect extensions
by resolving GPU SKUs (P5/P5e/H200 family), placing instances inside cluster placement
groups when `CloudInterconnect(kind=EFA, topology=RAIL_OPTIMIZED)` is requested, and
attaching FSx for Lustre as the shared-FS realisation of `CloudSharedFilesystem(kind=LUSTRE)`.
VPN bring-up is honoured by injecting Tailscale/Twingate cloud-init snippets into
`user_data` per [vpn-join-spec](../vpn-join-spec/design.md).

Every method on `AwsCloudProvisioner` accepts an `aspects: Aspects` parameter so the
caller controls retries, timeouts, persistence, and confirmation.  All AWS API
interaction is delegated to `automojo-interop-aws` and reuses the `boto3` session built
from an `AwsAccessKeyCredential`.  No direct `boto3.client(...)` calls exist outside
that interop layer.

---

## Requirements

### Requirement 1: Validate a Spec

**User Story:** As a coordinator, I want the AWS provisioner to validate a parsed
neutral spec before any `apply` runs, so that schema mismatches and unsupported
resource kinds fail loudly and quickly.

#### Acceptance Criteria

1. WHEN `validate(spec, aspects)` is called THE SYSTEM SHALL traverse every resource
   in the spec, dispatch each to its kind-specific validator, and return a
   `ValidationReport` enumerating errors and warnings.
2. WHEN the spec contains a `CloudObjectBucket` whose `region` is omitted THE SYSTEM
   SHALL report an error naming the resource.
3. WHEN the spec contains a `CloudSharedFilesystem(kind=WEKA)` THE SYSTEM SHALL report
   an error stating that AWS realises shared-FS through FSx for Lustre and that WEKA
   is supported only via marketplace AMI provisioning, which is out of scope for v1.
4. WHEN the spec requests `CloudInterconnect(kind=INFINIBAND_NDR)` THE SYSTEM SHALL
   report an error stating that AWS exposes only `EFA` for HPC interconnect.
5. WHEN every resource validates THE SYSTEM SHALL return a `ValidationReport` with
   `ok=True` and an empty `errors` list.

---

### Requirement 2: Plan a Spec

**User Story:** As a coordinator, I want the provisioner to compute a diff between the
spec and the live AWS account, so that I can review which resources will be created,
updated, or skipped before any change is applied.

#### Acceptance Criteria

1. WHEN `plan(spec, aspects)` is called THE SYSTEM SHALL perform a read-before-create
   query for every resource in the spec via the AWS interop client.
2. WHEN a resource is absent in AWS THE SYSTEM SHALL emit a `PlanAction(kind=CREATE)`
   carrying the resolved venue-native payload.
3. WHEN a resource is present and matches the spec (tag round-trip and attribute
   equality) THE SYSTEM SHALL emit a `PlanAction(kind=SKIP)`.
4. WHEN a resource is present but mutable attributes differ THE SYSTEM SHALL emit a
   `PlanAction(kind=UPDATE)` listing the attribute deltas.
5. WHEN the live account holds a resource carrying the spec's `automojo-run-id` tag
   that is not in the spec THE SYSTEM SHALL emit a `PlanAction(kind=DELETE)`.

---

### Requirement 3: Apply a Plan Idempotently

**User Story:** As a coordinator, I want `apply` to be safely re-runnable, so that a
mid-run failure can be recovered without duplicating resources.

#### Acceptance Criteria

1. WHEN `apply(spec, aspects)` is called THE SYSTEM SHALL first call `plan` and then
   execute actions in dependency order (network → subnet → SG → keypair → instance →
   volume → DNS).
2. WHEN re-applying a spec whose every resource is `SKIP` THE SYSTEM SHALL make no
   mutating AWS API calls and return a `ProvisioningResult` with `changed=False`.
3. WHEN an instance carries `vpn_join` THE SYSTEM SHALL render the cloud-init snippet
   from [vpn-join-spec](../vpn-join-spec/design.md) and prepend it to `user_data`.
4. WHEN `aspects.confirm` is `False` and the plan contains any `DELETE` THE SYSTEM
   SHALL refuse to apply and raise `ConfirmationRequiredError`.
5. WHEN an instance creation succeeds THE SYSTEM SHALL persist its instance-id under
   `.output/provisioning/<runid>/aws-inventory.json`.

---

### Requirement 4: Destroy in Reverse Order

**User Story:** As a coordinator, I want `destroy` to tear down the resources this
provisioner created, in reverse dependency order, so that orphans are not left behind.

#### Acceptance Criteria

1. WHEN `destroy(spec, aspects)` is called and `aspects.confirm` is `True` THE SYSTEM
   SHALL delete instances, then volumes, then security groups, then subnets, then
   networks tagged with the matching `automojo-run-id`.
2. WHEN a resource is already absent THE SYSTEM SHALL treat the deletion as a no-op
   success.
3. WHEN `aspects.confirm` is `False` THE SYSTEM SHALL refuse to destroy and raise
   `ConfirmationRequiredError`.
4. WHEN an instance carries `vpn_join` THE SYSTEM SHALL invoke
   `IVPNControlPlane.delete_device` for its overlay device record after the EC2
   termination call returns.

---

### Requirement 5: Inventory Existing Resources

**User Story:** As a coordinator, I want to enumerate every resource this provisioner
manages, so that `automojo-landscaping` can consume the result as a landscape file.

#### Acceptance Criteria

1. WHEN `inventory(spec, aspects)` is called THE SYSTEM SHALL query AWS for every
   resource carrying the `automojo-run-id` tag matching the spec.
2. WHEN inventory succeeds THE SYSTEM SHALL return a list of `ProvisionedResource`
   entries containing public IP, private IP, overlay IP (if known), and tags.

---

### Requirement 6: EFA + Placement Group for HPC

**User Story:** As a coordinator standing up a multi-node training cluster, I want
EFA-enabled ENIs and a cluster placement group, so that NCCL collectives run on the
fabric AWS provides for it.

#### Acceptance Criteria

1. WHEN an instance carries `CloudInterconnect(kind=EFA, topology=RAIL_OPTIMIZED)` THE
   SYSTEM SHALL create or reuse a cluster placement group whose name is derived from
   the spec's `apod` and attach the instance to it.
2. WHEN such an instance is created THE SYSTEM SHALL provision an EFA-enabled ENI and
   attach it as the primary network interface.
3. WHEN the requested instance family does not support EFA THE SYSTEM SHALL fail in
   `validate` with a message naming the resolved instance type.

---

### Requirement 7: FSx for Lustre

**User Story:** As a coordinator, I want `CloudSharedFilesystem(kind=LUSTRE)` to map to
FSx for Lustre, so that the shared filesystem is realised on AWS-native managed
storage.

#### Acceptance Criteria

1. WHEN the spec contains `CloudSharedFilesystem(kind=LUSTRE)` and `existing_id` is
   set THE SYSTEM SHALL look the file system up and attach the listed mount targets.
2. WHEN `existing_id` is absent THE SYSTEM SHALL fail with a "provision path not
   supported in v1" error per §7.6.
3. WHEN attaching mount targets THE SYSTEM SHALL render a cloud-init `runcmd` that
   installs the Lustre client and adds the `/etc/fstab` entry on each target instance.

---

### Requirement 8: GPU SKU Resolution

**User Story:** As a coordinator, I want neutral accelerator names (`H100_SXM`,
`H200_NVL`, `B200_SXM`) to resolve to AWS instance types, so that I don't have to
memorise the P5 family naming.

#### Acceptance Criteria

1. WHEN `CloudInstance.accelerators` contains a `CloudAcceleratorSpec` THE SYSTEM
   SHALL consult the `CloudAcceleratorCatalog` (§7.6) to resolve `model + count` to
   an AWS instance type.
2. WHEN no AWS SKU exists for the requested accelerator THE SYSTEM SHALL fail in
   `validate` naming the missing entry.
3. WHEN the resolved SKU disagrees with an explicitly supplied `CloudInstance.size`
   THE SYSTEM SHALL fail with a conflict error rather than silently overriding either.

---

### Requirement 9: Tag Round-Trip Fidelity

**User Story:** As a coordinator, I want neutral tags to survive a round trip through
AWS Tags, so that `plan` after `apply` reports no spurious diffs.

#### Acceptance Criteria

1. WHEN translating neutral `tags: List[Dict[str, str]]` to AWS `Tags` THE SYSTEM
   SHALL preserve every key and value verbatim.
2. WHEN reading AWS `Tags` back THE SYSTEM SHALL reconstruct the neutral form so that
   neutral → AWS → neutral is the identity for any tag set valid under the AWS tag
   character limits.
3. WHEN a tag value exceeds the AWS 256-character limit THE SYSTEM SHALL fail in
   `validate` rather than silently truncate.

---

### Requirement 10: Aspects on Every Call

**User Story:** As a coordinator, I want to pass timeouts, retries, persistence
backends, and confirmation flags per call, so that no provisioner method has hidden
behaviour.

#### Acceptance Criteria

1. WHEN any of `validate / plan / apply / destroy / inventory` is invoked THE SYSTEM
   SHALL accept an `Aspects` parameter and propagate it to the AWS interop client.
2. WHEN `aspects` is omitted THE SYSTEM SHALL substitute the default `Aspects()`
   instance — never silently retry or block indefinitely.
