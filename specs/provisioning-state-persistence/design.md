# Design

## Overview

The state-persistence layer is the on-disk record of every provisioning run.  It
makes apply resumable (combined with the lifecycle layer's idempotence contract) and
destroy clean (by handing the same inventory to the destroy verb that apply produced).

State lives under `.output/provisioning/`, the project-standard transient output
directory.  The layer is small: a couple of file-IO helpers, an atomic-write helper,
a YAML-safe serialiser, and an index file.

The atomic-write pattern is the load-bearing safety property: a crash during a long
provisioning run must never leave the directory in a state that confuses the next
resume.  Every state file is written via `write_tmp_then_rename`.

---

## Architecture

```
   .output/provisioning/
   ├── index.yaml                          (one line per run)
   ├── index.yaml.lock                     (advisory file lock)
   ├── <runid-1>/
   │   ├── spec.yaml
   │   ├── plan.yaml
   │   ├── result.yaml
   │   ├── inventory.yaml
   │   ├── landscape.yaml
   │   └── stages.log
   ├── <runid-2>.destroyed/                (renamed after clean destroy)
   │   └── ... same files ...
   └── ...

   Operations:
     create_run_dir(runid) -> Path
     load_run(runid)       -> RunState
     write_state(runid, state)
     mark_run_destroyed(runid)
```

---

## Data Model

```python
class RunStatus(Enum):
    STARTED   = "started"
    APPLIED   = "applied"
    FAILED    = "failed"
    DESTROYED = "destroyed"


class RunIndexEntry(SchemaObject):
    runid: str
    started: datetime
    finished: Optional[datetime]
    status: RunStatus
    spec_path: str
    venues: List[str]


class RunState(SchemaObject):
    runid: str
    spec: PipelineSpec
    plan: Optional[PipelinePlan]
    results: Dict[str, ProvisioningResult]      # venue_name -> result
    inventory: Dict[str, List[ProvisionedResource]]


class ProvisioningStateStore:
    def __init__(self, *, root: Path) -> None: ...

    def create_run(self, *, runid: str, spec_path: Path,
                   venues: List[str]) -> Path: ...

    def load_run(self, *, runid: str) -> RunState: ...

    def write_state(self, *, runid: str, state: RunState) -> None: ...

    def append_log(self, *, runid: str, line: str) -> None: ...

    def list_runs(self) -> List[RunIndexEntry]: ...

    def latest_run(self) -> Optional[RunIndexEntry]: ...

    def mark_destroyed(self, *, runid: str) -> None: ...
```

---

## Atomic Write

```python
def write_tmp_then_rename(*, path: Path, content: str) -> None:
    """
        Write content to <path>.tmp then atomically rename to <path>.
        Guarantees readers never see a partial file even on crash mid-write.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content)
    os.replace(tmp, path)
    return
```

All YAML files in the run directory use this helper.  `stages.log` uses append-only
writes (one line per stage transition) and does not require atomic rename.

---

## Secret Scrubbing

A small `redact_for_persistence(obj)` helper walks any `SchemaObject` and:

- Replaces fields marked `sensitive` with the literal string `"<redacted>"`.
- Replaces credential objects with the vault name only.
- Truncates strings longer than the `sensitive_max_keep_chars` threshold to their
  first 6 characters + length suffix (used for fingerprints in logs).

`spec.yaml`, `result.yaml`, and `inventory.yaml` are all passed through the redactor
before being serialised.

---

## Locking

A file lock on `index.yaml.lock` is taken when the run starts and released when the
engine exits (normal or exceptional).  Implementation uses `fcntl.flock` on POSIX
and `msvcrt.locking` on Windows; both wrapped in a single `cross_platform_lock`
context manager.

Lock timeout is controlled by `aspects.lock_timeout_seconds` (default 30s).

---

## Module Layout

```
source/packages/automojo/provisioning/state/
├── provisioningstatestore.py
├── runstate.py
├── runstatus.py
├── runindexentry.py
├── atomicwrite.py
├── redactforpersistence.py
└── crossplatformlock.py
```

---

## See Also

- [provisioning-engine-pipeline](../provisioning-engine-pipeline/design.md) — main
  consumer.
- [cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md) — produces
  the `ProvisioningResult` and `ProvisionedResource` records.
- [landscape-inventory-emit](../landscape-inventory-emit/design.md) — consumes
  `inventory.yaml` to produce `landscape.yaml`.

---

## Testing Strategy

- **Unit tests** — `write_tmp_then_rename` round-trip; rename atomicity verified by
  killing mid-write in a subprocess and asserting the final file is either fully
  the new content or absent.
- **Resume tests** — start a run, write partial state, terminate, restart with the
  same runid, assert the engine reads the partial state correctly.
- **Destroy reads state** — destroy with a runid, assert it reads `inventory.yaml`
  and ignores `spec.yaml`.
- **Destroy without runid** — assert `SemanticError`.
- **Lock contention test** — second engine instance waits for the lock and times
  out per aspects.
- **Secret-scrubbing test** — write a state that contains a credential object; load
  the persisted YAML and assert the secret value is absent.
- No property tests required at this layer — invariants are point-wise, not
  algebraic.
