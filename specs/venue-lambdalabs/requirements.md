# Requirements — Lambda Labs Provisioner

## Introduction

The `venue-lambdalabs` feature provides `codecraftai-provisioning` with the ability
to stand up GPU instances on Lambda Labs.  It implements the `CloudProvisioner`
lifecycle defined in
[cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md) and maps the
neutral resource model in [cloud-resource-model](../cloud-resource-model/design.md)
onto Lambda Labs primitives via the Lambda Labs Cloud REST API surfaced by
`codecraftai-interop-lambdalabs` (built on `codecraftai-restclient-base`).

Lambda's API is intentionally small: instances, SSH keys, file-systems (shared
NFS), and 1-Click Clusters.  There is no VPC, no firewall, and no object
storage in the v1 API surface.  The provisioner is therefore honest about this
in `validate`:

- `CloudNetwork` / `CloudSubnet` / `CloudSecurityGroup` / `CloudKeyPair` →
  honoured (SSH key) but VPC/subnet/SG asks are recorded as warnings and
  ignored.
- `CloudObjectBucket` / `CloudLoadBalancer` / `CloudDnsRecord` →
  `validate`-error.
- `CloudInterconnect(kind in {INFINIBAND_*})` → realised by selecting a
  1-Click Cluster offering for the requested GPU type.
- `CloudSharedFilesystem(kind=VENUE_NATIVE, existing_id=...)` → Lambda
  file-system attach; new provisioning out of scope per §7.6.

Every method on `LambdalabsCloudProvisioner` accepts `aspects: Aspects`.

---

## Requirements

### Requirement 1: Validate a Spec

#### Acceptance Criteria

1. WHEN `validate(spec, aspects)` is called THE SYSTEM SHALL ensure every
   Instance's `region` and `instance_type` resolve to a Lambda region and
   SKU.
2. WHEN the spec contains `CloudObjectBucket`, `CloudLoadBalancer`, or
   `CloudDnsRecord` THE SYSTEM SHALL report errors.
3. WHEN the spec contains `CloudNetwork`, `CloudSubnet`, or
   `CloudSecurityGroup` THE SYSTEM SHALL emit a warning explaining Lambda
   exposes no VPC/firewall and these resources are ignored.
4. WHEN the requested accelerator + interconnect resolves to a 1-Click
   Cluster offering THE SYSTEM SHALL note that path in the plan output.

---

### Requirement 2: Plan

#### Acceptance Criteria

1. WHEN `plan(spec, aspects)` is called THE SYSTEM SHALL list Instances by
   `name` matching `<spec-name>-<run-id-short>` and emit `PlanAction`s.
2. WHEN Lambda offers no live-update of instance_type THE SYSTEM SHALL flag
   instance_type drift as UPDATE-by-recreate.

---

### Requirement 3: Apply Idempotently

#### Acceptance Criteria

1. WHEN `apply(spec, aspects)` is called THE SYSTEM SHALL ensure SSH Keys are
   uploaded → ensure file-system attach-list is current → launch Instance
   (single or 1-Click Cluster).
2. WHEN re-applying THE SYSTEM SHALL make no mutating calls when every action
   is SKIP.
3. WHEN an Instance carries `vpn_join` THE SYSTEM SHALL render the cloud-init
   snippet from [vpn-join-spec](../vpn-join-spec/design.md) into the
   `user_data` field of the launch request.
4. WHEN any DELETE is planned and `aspects.confirm` is false THE SYSTEM SHALL
   raise `ConfirmationRequiredError`.

---

### Requirement 4: Destroy

#### Acceptance Criteria

1. WHEN `destroy(spec, aspects)` is called with confirm THE SYSTEM SHALL
   terminate Instances by name and detach file-systems (Lambda manages
   file-system lifecycle outside this provisioner).
2. WHEN VPN-joined Instances are terminated THE SYSTEM SHALL invoke
   `IVPNControlPlane.delete_device`.

---

### Requirement 5: Inventory

#### Acceptance Criteria

1. WHEN `inventory(spec, aspects)` is called THE SYSTEM SHALL list Instances
   by name prefix matching the run-id and emit `ProvisionedResource` records.

---

### Requirement 6: GPU SKU + 1-Click Cluster Resolution

#### Acceptance Criteria

1. WHEN a `CloudAcceleratorSpec` resolves to a Lambda single-instance SKU
   (e.g. `gpu_1x_h100_pcie`, `gpu_8x_h100_sxm5`) THE SYSTEM SHALL launch a
   single Instance.
2. WHEN the same neutral spec asks for multi-node InfiniBand and Lambda
   offers a 1-Click Cluster for that SKU THE SYSTEM SHALL invoke the
   1-Click Cluster API instead.
3. WHEN the requested accelerator has no Lambda SKU THE SYSTEM SHALL fail in
   `validate`.

---

### Requirement 7: Tag Round-Trip Fidelity

#### Acceptance Criteria

1. WHEN translating neutral tags THE SYSTEM SHALL encode them into the
   Instance `name` suffix and a stored sidecar JSON under
   `.output/provisioning/<runid>/lambdalabs-tags.json`, since Lambda's API
   has no native tag field.
2. WHEN reading sidecar JSON back THE SYSTEM SHALL recover the neutral tag
   list such that round-tripping is the identity.

---

### Requirement 8: Aspects on Every Call

#### Acceptance Criteria

1. WHEN any provisioner method is invoked THE SYSTEM SHALL accept and propagate
   `Aspects`.
2. WHEN omitted THE SYSTEM SHALL substitute the default `Aspects()`.
