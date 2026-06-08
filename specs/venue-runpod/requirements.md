# Requirements — RunPod Workload Provisioner

## Introduction

The `venue-runpod` feature provides `codecraftai-provisioning` with the ability
to stand up container-shaped GPU workloads on RunPod.  It implements the
**`WorkloadProvisioner`** lifecycle per PLAN §7.2 (`validate / plan / apply /
destroy / inventory`) on Pod templates and persistent Network Volumes.  All
API calls go through `codecraftai-interop-runpod` against the RunPod GraphQL
endpoint.

RunPod is container-shaped, not VM-shaped: there is no concept of a network,
subnet, security group, or per-pod firewall in the API.  The unit of work is
a **Pod** (a container, not a Kubernetes Pod) bound to a GPU type and a
template image.  RunPod distinguishes Secure Cloud (vetted DCs) from
Community Cloud (peered providers); the provisioner honours the requested
tier.

Honest-fit notes:

- `CloudNetwork` / `CloudSubnet` / `CloudSecurityGroup` / `CloudKeyPair`
  → not realised (warning at validate).
- `CloudObjectBucket` / `CloudLoadBalancer` / `CloudDnsRecord` →
  `validate`-error.
- `CloudInterconnect(kind != NONE)` → `validate`-error (RunPod offers no
  inter-pod IB fabric in the API).
- `CloudSharedFilesystem(VENUE_NATIVE, existing_id)` → Network Volume
  attach; new volume provisioning supported as a separate Network Volume
  CREATE.

Every method on `RunpodWorkloadProvisioner` accepts `aspects: Aspects`.

---

## Requirements

### Requirement 1: Validate a Spec

#### Acceptance Criteria

1. WHEN `validate(spec, aspects)` is called THE SYSTEM SHALL ensure every
   Pod has a resolvable RunPod `gpuTypeId` and `templateId` (or an inline
   image).
2. WHEN the spec requests Secure Cloud and no Secure Cloud capacity exists
   for the GPU type in the requested region THE SYSTEM SHALL fail with a
   capacity error.
3. WHEN the spec contains `CloudObjectBucket`, `CloudLoadBalancer`,
   `CloudDnsRecord`, or `CloudInterconnect != NONE` THE SYSTEM SHALL report
   errors.
4. WHEN `CloudNetwork`/`CloudSubnet`/`CloudSecurityGroup` are present THE
   SYSTEM SHALL warn that RunPod exposes none of these.

---

### Requirement 2: Plan

#### Acceptance Criteria

1. WHEN `plan(spec, aspects)` is called THE SYSTEM SHALL list Pods and
   Network Volumes filtered by name prefix `<spec-name>-<run-id-short>`
   and emit `PlanAction`s.
2. WHEN GPU type or template drifts THE SYSTEM SHALL flag
   UPDATE-by-recreate.

---

### Requirement 3: Apply Idempotently

#### Acceptance Criteria

1. WHEN `apply(spec, aspects)` is called THE SYSTEM SHALL ensure Network
   Volumes exist → launch Pods, binding each Pod to the appropriate volume
   list.
2. WHEN re-applying THE SYSTEM SHALL make no mutating calls when every
   action is SKIP.
3. WHEN a Pod carries `vpn_join` THE SYSTEM SHALL render the cloud-init
   snippet from [vpn-join-spec](../vpn-join-spec/design.md) into the Pod's
   `dockerArgs` or `containerStartScript` so the `tailscale up` daemon
   starts at container boot (Tailscale userspace mode is required because
   RunPod containers lack `NET_ADMIN` by default).
4. WHEN any DELETE is planned and `aspects.confirm` is false THE SYSTEM
   SHALL raise `ConfirmationRequiredError`.

---

### Requirement 4: Destroy

#### Acceptance Criteria

1. WHEN `destroy(spec, aspects)` is called with confirm THE SYSTEM SHALL
   stop and terminate Pods then delete Network Volumes owned by the
   run-id.
2. WHEN VPN-joined Pods are terminated THE SYSTEM SHALL invoke
   `IVPNControlPlane.delete_device`.

---

### Requirement 5: Inventory

#### Acceptance Criteria

1. WHEN `inventory(spec, aspects)` is called THE SYSTEM SHALL list Pods and
   Volumes by name prefix and emit `ProvisionedResource` records carrying
   the Pod's public IP (when allocated) and the overlay IP (when known).

---

### Requirement 6: Secure Cloud vs Community Cloud Tier

#### Acceptance Criteria

1. WHEN the spec sets `tier="secure"` THE SYSTEM SHALL launch Pods in
   Secure Cloud.
2. WHEN `tier="community"` is set THE SYSTEM SHALL launch in Community
   Cloud.
3. WHEN no tier is set THE SYSTEM SHALL default to `secure` and emit an
   informational note.

---

### Requirement 7: Tag Round-Trip Fidelity

#### Acceptance Criteria

1. WHEN translating neutral tags THE SYSTEM SHALL encode them into the
   Pod `name` suffix and a sidecar JSON under
   `.output/provisioning/<runid>/runpod-tags.json`, since RunPod's API has
   no native tag field.
2. WHEN reading sidecar JSON back THE SYSTEM SHALL recover the neutral tag
   list such that round-tripping is the identity.

---

### Requirement 8: Aspects on Every Call

#### Acceptance Criteria

1. WHEN any provisioner method is invoked THE SYSTEM SHALL accept and
   propagate `Aspects`.
2. WHEN omitted THE SYSTEM SHALL substitute the default `Aspects()`.
