# Requirements

## Introduction

Spot / preemptible / interruptible instances complicate the idempotence story: a
venue can reclaim them at any time, leaving `inventory` in a state the framework
didn't choose.  Per the §7.6 plan decision, the framework adopts a **fail-loud
default** — `CloudInstance.preemption_policy = "FAIL"` — and forces the user to opt
in to other behaviour by setting the policy explicitly.

This spec defines the policy enum, the per-venue obligations on plugins, and the
expected behaviour during `apply / verify / inventory / destroy` for each value.

The rationale (per the plan): silent reacquisition during `apply` would mask capacity
problems behind quietly-degraded reruns; users on spot capacity who *want* auto-
reacquire opt in explicitly.

---

## Requirements

### Requirement 1: PreemptionPolicy Enum

**User Story:** As a provisioning author, I want to declare what should happen when
the venue reclaims a spot instance.

#### Acceptance Criteria

1. THE SYSTEM SHALL define `preemption_policy` on `CloudInstance` as
   `Literal["FAIL", "REACQUIRE", "BEST_EFFORT"]` with default `"FAIL"`.
2. WHEN any other value is supplied THE SYSTEM SHALL raise
   `SchemaValidationError` at construction.
3. THE SYSTEM SHALL surface the policy on the emitted landscape device entry so
   downstream coordinators know the instance may disappear.

---

### Requirement 2: FAIL Behaviour

**User Story:** As a user on on-demand capacity, I want any unexpected preemption to
fail loudly.

#### Acceptance Criteria

1. WHEN `apply` notices a previously-applied instance has been preempted (its
   `venue_id` no longer resolves) and policy is `FAIL` THE SYSTEM SHALL raise
   `ProvisioningPreemptionError` listing the instance.
2. WHEN `verify` polls an instance and finds it terminated and policy is `FAIL`
   THE SYSTEM SHALL raise `ProvisioningPreemptionError`.
3. THE SYSTEM SHALL emit a clear error message identifying the instance, the
   reason, and the policy in effect.

---

### Requirement 3: REACQUIRE Behaviour

**User Story:** As a user on spot capacity that I want auto-replaced, I want the
engine to bring up a replacement under the same `name`.

#### Acceptance Criteria

1. WHEN `apply` notices a preempted instance and policy is `REACQUIRE` THE SYSTEM
   SHALL create a replacement instance with the same spec.
2. THE SYSTEM SHALL log a `WARNING` for every reacquisition event with the original
   `venue_id` and the new one.
3. THE SYSTEM SHALL update `inventory.yaml` to reflect the new `venue_id`.
4. WHERE `REACQUIRE` succeeds THE SYSTEM SHALL preserve the instance's tags and
   re-inject the cloud-init payload via the same renderer.

---

### Requirement 4: BEST_EFFORT Behaviour

**User Story:** As a user running fault-tolerant workloads (training with
checkpointing, batch jobs), I want preempted instances dropped from the inventory
without failing the whole apply.

#### Acceptance Criteria

1. WHEN `apply` notices a preempted instance and policy is `BEST_EFFORT` THE SYSTEM
   SHALL drop the instance from the inventory and continue.
2. THE SYSTEM SHALL log an `INFO` event recording the drop.
3. WHEN the resulting inventory falls below a user-declared `min_count` (future v1.5
   addition) THE SYSTEM SHALL still succeed and surface the count on the landscape
   emit.

---

### Requirement 5: Venue Plugin Obligations

**User Story:** As a venue-plugin author, I want clear obligations for each policy.

#### Acceptance Criteria

1. THE SYSTEM SHALL require every venue provisioner that supports preemptible
   instances to honour all three policy values.
2. WHERE a venue does not support spot/preemptible capacity at all (e.g. some bare
   metal venues) THE SYSTEM SHALL accept the policy field but treat all values
   identically (the instance will never be preempted).
3. THE SYSTEM SHALL publish a `supports_preemption() -> bool` capability per venue
   used by the spec validator for documentation purposes.

---

### Requirement 6: Destroy Interaction

**User Story:** As a user, I want destroy to behave sensibly regardless of policy.

#### Acceptance Criteria

1. WHEN `destroy` runs and the inventory references an already-preempted instance
   THE SYSTEM SHALL log and continue (idempotent destroy) regardless of policy.
2. WHEN `destroy` runs while `REACQUIRE` is in effect THE SYSTEM SHALL NOT attempt
   any reacquisition during the destroy path.
