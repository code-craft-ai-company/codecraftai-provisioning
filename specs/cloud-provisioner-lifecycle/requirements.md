# Requirements

## Introduction

`CloudProvisioner` is the abstract base every venue plugin extends.  It defines five
lifecycle verbs — `validate`, `plan`, `apply`, `destroy`, `inventory` — that the
provisioning engine drives in fixed order.  The class is venue-agnostic: it owns the
shape of the lifecycle, the typed plan/result/inventory dataclasses, and the
**idempotency contract** that every subclass must honour.

The plan's §5 "idempotency budget" decision is non-negotiable: read-before-create on
every resource, every venue, no exceptions.  That decision lives in this spec as
contract-level requirements, with property-based tests that prove subclasses can
re-apply a plan without duplicating resources and that `destroy ∘ apply` returns the
inventory to its pre-apply state.

Per §8 every method takes a named `aspects` parameter.  No behaviour-modifying
decorators.  No baked-in retries.

---

## Requirements

### Requirement 1: Abstract Base Class

**User Story:** As a venue-plugin author, I want a single abstract base I subclass.

#### Acceptance Criteria

1. THE SYSTEM SHALL expose `CloudProvisioner` as an abstract base with abstract
   methods: `validate(*, aspects)`, `plan(*, aspects) -> ProvisioningPlan`,
   `apply(*, aspects) -> ProvisioningResult`, `destroy(*, aspects) -> None`,
   `inventory(*, aspects) -> List[ProvisionedResource]`.
2. THE SYSTEM SHALL require every method to accept `aspects` as a named-only
   parameter.
3. THE SYSTEM SHALL forbid any behaviour-modifying decorator on lifecycle methods.

---

### Requirement 2: Validate Stage

**User Story:** As a framework author, I want validate to catch every shape and
semantic error before any side effect.

#### Acceptance Criteria

1. WHEN `validate` runs THE SYSTEM SHALL check every shape and cross-resource
   semantic invariant from the model specs (CIDR containment, sibling non-overlap,
   accelerator support, VPN join validity, mount target resolution).
2. WHEN validation fails THE SYSTEM SHALL raise `SchemaSemanticError` with a
   multi-line message enumerating every offending resource (not just the first).
3. WHEN validation succeeds THE SYSTEM SHALL return `None`.
4. THE SYSTEM SHALL NOT make any remote API call during validate.

---

### Requirement 3: Plan Stage

**User Story:** As a framework author, I want a dry-run that returns intended
actions without touching the venue.

#### Acceptance Criteria

1. WHEN `plan` runs THE SYSTEM SHALL read the current venue state and compute a
   `ProvisioningPlan` listing per-resource intents (`CREATE`, `UPDATE`, `SKIP`,
   `DELETE`).
2. THE SYSTEM SHALL NOT mutate venue state during plan.
3. WHEN a resource already exists with matching shape THE SYSTEM SHALL emit `SKIP`.
4. WHEN a resource exists with a different shape THE SYSTEM SHALL emit `UPDATE` and
   include the diff.

---

### Requirement 4: Apply Stage — Idempotence

**User Story:** As a CI operator, I want `apply` to be safe to rerun any number of
times.

#### Acceptance Criteria

1. WHEN `apply` runs against a venue with no matching state THE SYSTEM SHALL create
   every resource and return a `ProvisioningResult` listing the newly created ids.
2. WHEN `apply` runs against a venue where all resources already match the spec THE
   SYSTEM SHALL make no mutating API call and SHALL return the existing inventory.
3. WHERE the plan contains an `UPDATE` intent THE SYSTEM SHALL apply the update via
   the venue API without recreating the resource.
4. THE SYSTEM SHALL satisfy the algebraic identity `apply ∘ apply = apply` —
   re-applying a plan produces the same inventory as applying once.

---

### Requirement 5: Destroy Stage — Inversibility

**User Story:** As a CI operator, I want `destroy` to cleanly tear down everything
`apply` brought up.

#### Acceptance Criteria

1. WHEN `destroy` runs against the inventory produced by a prior `apply` THE SYSTEM
   SHALL remove every resource in reverse dependency order.
2. THE SYSTEM SHALL satisfy `destroy ∘ apply = nop` — after applying then
   destroying, the venue inventory matches the pre-apply state.
3. WHEN `destroy` runs against an already-empty venue THE SYSTEM SHALL succeed
   silently.
4. WHERE `aspects.confirm` is `False` THE SYSTEM SHALL refuse to run and raise
   `SemanticError`.

---

### Requirement 6: Inventory Stage

**User Story:** As a framework author, I want to enumerate everything currently
provisioned without parsing logs.

#### Acceptance Criteria

1. WHEN `inventory` runs THE SYSTEM SHALL return a list of `ProvisionedResource`
   objects, each carrying `kind`, `name`, `venue_id`, `attributes`, and `tags`.
2. THE SYSTEM SHALL identify resources owned by automojo via a stable tag set the
   subclass applies on creation.
3. THE SYSTEM SHALL be safe to call after a failed apply (partial inventory is
   surfaced as-is, not as an error).

---

### Requirement 7: Shared Dataclasses

**User Story:** As a framework author, I want one shared shape for plan / result /
inventory across every venue.

#### Acceptance Criteria

1. THE SYSTEM SHALL expose `ProvisioningPlan(actions: List[PlannedAction])`.
2. THE SYSTEM SHALL expose `PlannedAction(intent, resource_kind, resource_name,
   diff: Dict[str, Any])` with `intent ∈ {CREATE, UPDATE, SKIP, DELETE}`.
3. THE SYSTEM SHALL expose `ProvisioningResult(created: List[ProvisionedResource],
   updated: List[ProvisionedResource], skipped: List[str], errors: List[Dict])`.
4. THE SYSTEM SHALL expose `ProvisionedResource(kind, name, venue_id, attributes,
   tags)` as a `SchemaObject` so the inventory is serialisable to YAML.

---

### Requirement 8: Property-Test Invariants ⊙

**User Story:** As a maintainer, I want the idempotence and inversibility properties
proven by property tests on every venue mock.

#### Acceptance Criteria

1. THE SYSTEM SHALL include property tests asserting:
   - **Apply idempotence:** for any randomly-generated valid plan, applying twice
     in succession produces inventories with identical sets of `venue_id`s.
   - **Destroy inversibility:** for any randomly-generated valid plan, the venue
     mock's inventory before-apply and after-destroy match.
   - **Plan stability:** computing a plan twice in a row produces equal
     `PlannedAction` lists.
2. THE SYSTEM SHALL run these property tests against a `FakeCloudProvisioner`
   subclass that simulates a venue in-memory.
