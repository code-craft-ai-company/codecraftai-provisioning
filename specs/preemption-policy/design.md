# Design

## Overview

The preemption policy is a single typed field on `CloudInstance` that tells the
framework how to react when the venue reclaims an instance.  The §7.6 plan decision
makes `FAIL` the default precisely because a silent reacquisition during `apply`
would hide capacity problems behind quietly-degraded reruns.  Users that want spot
behaviour opt in by setting the policy explicitly.

The implementation is mostly a contract: venue provisioners observe the policy at
two points — during apply's match-then-act (when reading state) and during verify
(when waiting for `running`).  Both points consult a small helper module that
encodes the policy's branches.

---

## Architecture

```
   spec author
       │
       │ CloudInstance(preemption_policy="FAIL"|"REACQUIRE"|"BEST_EFFORT")
       ▼
   pipeline validate ─► (no behaviour difference here)
       │
       ▼
   pipeline apply
       │
       │ provisioner._ensure_instance(...)
       │       │
       │       │ read existing venue state
       │       ▼
       │   if venue_id known but resource missing:
       │       handle_preemption(spec=instance, policy=policy,
       │                         aspects=aspects)
       │
       ▼
   pipeline verify
       │
       │ poll until running
       │       │
       │       │ if instance terminated:
       │       │     handle_preemption(...)
       ▼
   pipeline emit
       │
       └─► landscape device entry includes preemption_policy
```

---

## Data Model

```python
class PreemptionPolicy(Enum):
    FAIL        = "FAIL"
    REACQUIRE   = "REACQUIRE"
    BEST_EFFORT = "BEST_EFFORT"


class ProvisioningPreemptionError(Exception):
    """Raised when a FAIL-policy instance is preempted."""


class PreemptionEvent(SchemaObject):
    instance_name: str
    venue_id: str
    detected_at_stage: Literal["apply", "verify", "destroy"]
    original_venue_id: Optional[str]
    replacement_venue_id: Optional[str]
    policy: PreemptionPolicy


def handle_preemption(*, spec: CloudInstance,
                      policy: PreemptionPolicy,
                      provisioner: CloudProvisioner,
                      stage: Literal["apply", "verify"],
                      aspects: Aspects) -> Optional[ProvisionedResource]:
    """
        Apply the policy's branch.

        :returns: a ProvisionedResource for the replacement instance when policy is
                  REACQUIRE; None when policy is BEST_EFFORT; raises
                  ProvisioningPreemptionError when policy is FAIL.
    """
```

---

## Policy Branches

| Policy        | Apply behaviour                                  | Verify behaviour                                 | Destroy behaviour |
| ------------- | ------------------------------------------------ | ------------------------------------------------ | ----------------- |
| `FAIL`        | raise `ProvisioningPreemptionError`              | raise `ProvisioningPreemptionError`              | log + continue    |
| `REACQUIRE`   | recreate instance with same spec, new venue_id   | recreate instance with same spec, new venue_id   | log + continue    |
| `BEST_EFFORT` | drop from inventory, log INFO                    | drop from inventory, log INFO                    | log + continue    |

Reacquisition reuses the existing cloud-init renderer; the auth-key mint may be
re-issued if the original ephemeral key has already expired (which is the common
case).

---

## Venue Capability

```python
class CloudProvisioner(ABC):
    @classmethod
    def supports_preemption(cls) -> bool:
        """
            Whether this venue offers spot / preemptible / interruptible capacity.
            Used at validate-time for documentation; does not change behaviour
            (the policy field is honoured on every venue).
        """
        return False
```

Venues that override this to `True`: AWS (Spot), Azure (Spot VMs), GCP
(Preemptible/Spot VMs), Oracle (Preemptible), Lambda Labs (interruptible).  All
others default to `False`.

---

## Module Layout

```
source/packages/automojo/provisioning/preemption/
├── preemptionpolicy.py
├── preemptionevent.py
├── preemptionhandler.py        # handle_preemption()
└── preemptionerrors.py         # ProvisioningPreemptionError
```

---

## See Also

- [cloud-resource-model](../cloud-resource-model/design.md) — `preemption_policy`
  field on `CloudInstance`.
- [cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md) — match-
  then-act helpers that consult the policy.
- [provisioning-engine-pipeline](../provisioning-engine-pipeline/design.md) — calls
  the handler from apply and verify stages.
- [landscape-inventory-emit](../landscape-inventory-emit/design.md) — emits the
  policy on each device entry.
- [cloud-init-injection](../cloud-init-injection/design.md) — re-rendered on
  REACQUIRE.

---

## Testing Strategy

- **Unit tests** — assert default is `FAIL`; reject invalid strings; serialise
  through `to_dict / from_dict`.
- **FAIL-branch test** — Fake provisioner with a "preempted" record; assert
  `handle_preemption` raises `ProvisioningPreemptionError` with the documented
  message shape.
- **REACQUIRE-branch test** — Fake provisioner; assert a replacement
  `ProvisionedResource` is created with the same `name` and a new `venue_id`;
  assert WARNING is logged.
- **BEST_EFFORT-branch test** — Fake provisioner; assert handler returns `None`
  and the instance is dropped from the next `inventory()` call.
- **Destroy-during-REACQUIRE test** — assert no reacquisition happens on destroy.
- **Landscape emit test** — assert the policy appears on every emitted device entry.
- No property tests required at this layer.
