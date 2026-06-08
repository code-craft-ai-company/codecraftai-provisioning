# Design

## Overview

`CloudProvisioner` defines the lifecycle contract every venue subclass implements.
The five-verb shape — `validate / plan / apply / destroy / inventory` — is the same
contract the provisioning engine pipeline drives stage-by-stage for both
`CloudProvisioner` and `WorkloadProvisioner` subclasses.

The two heavy contracts the base class enforces (via documentation, abstract method
signatures, and a `FakeCloudProvisioner` reference implementation used in tests):

- **Idempotence** — `apply ∘ apply = apply`.  Required by the §5 "idempotency budget"
  decision.  Subclasses achieve this with read-before-create on every resource and by
  matching existing venue state against the desired spec.
- **Inversibility** — `destroy ∘ apply = nop` (modulo external state that wasn't part
  of the spec).  Required so test runs in CI can clean up after themselves.

Both contracts are proven by property tests in this spec (run against the in-memory
fake).  Every venue subclass is expected to *also* re-run the same property test suite
against its own mock SDK to demonstrate the contract holds on real venue shapes.

---

## Architecture

```
   ProvisioningEngine
       │
       │ validate ─► CloudProvisioner.validate(aspects)        [no I/O]
       │ plan     ─► CloudProvisioner.plan(aspects) ─► Plan    [reads venue]
       │ apply    ─► CloudProvisioner.apply(aspects) ─► Result [reads + creates]
       │ destroy  ─► CloudProvisioner.destroy(aspects)         [destroys]
       │ inventory─► CloudProvisioner.inventory(aspects) ─► [] [reads venue]
       ▼
   Subclasses:
     AwsCloudProvisioner   AzureCloudProvisioner   ...
     FakeCloudProvisioner  (in-memory, used by property tests)
```

---

## Data Model

```python
class PlannedActionIntent(Enum):
    CREATE = "create"
    UPDATE = "update"
    SKIP   = "skip"
    DELETE = "delete"


class PlannedAction(SchemaObject):
    intent: PlannedActionIntent
    resource_kind: str
    resource_name: str
    diff: Dict[str, Any]


class ProvisioningPlan(SchemaObject):
    actions: List[PlannedAction]


class ProvisionedResource(SchemaObject):
    kind: str
    name: str
    venue_id: str
    attributes: Dict[str, Any]
    tags: List[Dict[str, str]]


class ProvisioningResult(SchemaObject):
    created: List[ProvisionedResource]
    updated: List[ProvisionedResource]
    skipped: List[str]
    errors: List[Dict[str, Any]]


class CloudProvisioner(ABC):
    OWNER_TAG_KEY: str = "ccai:owned-by"
    OWNER_TAG_VALUE: str = "codecraftai-provisioning"

    def __init__(self, *, venue: CloudVenue, spec: CloudProvisioningSpec) -> None:
        self._venue = venue
        self._spec = spec
        return

    @abstractmethod
    def validate(self, *, aspects: Aspects) -> None: ...

    @abstractmethod
    def plan(self, *, aspects: Aspects) -> ProvisioningPlan: ...

    @abstractmethod
    def apply(self, *, aspects: Aspects) -> ProvisioningResult: ...

    @abstractmethod
    def destroy(self, *, aspects: Aspects) -> None: ...

    @abstractmethod
    def inventory(self, *, aspects: Aspects) -> List[ProvisionedResource]: ...
```

---

## Idempotence Pattern

Subclasses implement a shared **match-then-act** pattern for every resource kind:

```python
def _ensure_network(self, *, desired: CloudNetwork, aspects: Aspects) -> ProvisionedResource:
    existing = self._read_network_by_tag(desired=desired, aspects=aspects)
    if existing is None:
        created = self._create_network(desired=desired, aspects=aspects)
        rtnval = created
    elif not self._network_matches(existing=existing, desired=desired):
        updated = self._update_network(existing=existing, desired=desired, aspects=aspects)
        rtnval = updated
    else:
        rtnval = existing
    return rtnval
```

The base class provides:

- `OWNER_TAG_KEY / OWNER_TAG_VALUE` — applied to every created resource.
- `_planned_action_for(...)` helper used by `plan` to translate match-then-act
  outcomes into `PlannedAction` records without performing the side effect.

---

## Destroy Order

The base class exposes `_destroy_order(plan: ProvisioningPlan) -> List[PlannedAction]`
that reverses the resource-dependency topological sort used by the engine pipeline
(see [provisioning-engine-pipeline](../provisioning-engine-pipeline/design.md)).
Subclasses do not implement ordering themselves.

`destroy` honours the §plan-and-apply `confirm=True` aspect: without it, the base
class raises `SemanticError` before dispatching to any subclass code.  This prevents
accidental destruction in interactive contexts.

---

## Module Layout

```
source/packages/ccai/provisioning/model/cloud/
├── cloudprovisioner.py                # abstract base (fleshed out)
├── plannedaction.py
├── plannedactionintent.py
├── provisioningplan.py
├── provisionedresource.py
└── provisioningresult.py

source/packages/ccai/provisioning/model/cloud/_fake/
└── fakecloudprovisioner.py            # in-memory subclass for property tests
```

---

## FakeCloudProvisioner

Used in property tests for this spec and re-exported for venue plugins to compose into
their own test suites.  Implementation sketch:

- Holds a `Dict[(kind, name), ProvisionedResource]` as the "venue".
- `validate` runs all model-level semantic checks.
- `plan` reads the dict, computes diffs.
- `apply` mutates the dict, returns the result.
- `destroy` empties the dict (with `confirm` gating).
- `inventory` returns the dict's values.

The fake is the reference implementation for the idempotence and inversibility
contracts.  If a venue subclass cannot satisfy the property test against its own
SDK mock with the same shape, it is non-conforming and the bug is in the subclass.

---

## See Also

- [cloud-resource-model](../cloud-resource-model/design.md) — model classes consumed.
- [accelerator-and-interconnect-model](../accelerator-and-interconnect-model/design.md)
  — additional fields on `CloudInstance`.
- [provisioning-engine-pipeline](../provisioning-engine-pipeline/design.md) — drives
  the five verbs in stage order.
- [provisioning-state-persistence](../provisioning-state-persistence/design.md) —
  writes `ProvisioningResult` to disk.
- [workload-venue-model](../workload-venue-model/design.md) — sibling lifecycle.
- `codecraftai-interfaces/specs/task-handle-protocol` — used by async venue APIs.

---

## Testing Strategy

- **Unit tests** — construct `PlannedAction`, `ProvisioningPlan`,
  `ProvisioningResult`, `ProvisionedResource`; assert round-trip via SchemaObject.
- **Fake provisioner tests** — drive `FakeCloudProvisioner` through every verb,
  assert the documented post-conditions.
- **Confirm-gating test** — `destroy` without `aspects.confirm=True` raises
  `SemanticError` before any subclass call.
- **Property tests (`hypothesis`) ⊙:**
  - **Apply idempotence:** `apply(plan); apply(plan)` produces inventories whose
    `(kind, name, venue_id)` sets are equal.
  - **Destroy inversibility:** for any valid spec, `inventory()` before any apply
    equals `inventory()` after `apply(); destroy(confirm=True)`.
  - **Plan stability:** `plan() == plan()` when no out-of-band mutation has
    happened between calls.
  - **Tag-ownership invariant:** every resource present after `apply` carries the
    owner tag; resources without the tag are not destroyed.
- Strategies generate small but rich specs combining networks, subnets, SGs,
  instances, and DNS records.
