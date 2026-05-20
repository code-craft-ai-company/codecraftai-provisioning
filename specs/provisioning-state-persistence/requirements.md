# Requirements

## Introduction

Every provisioning run produces a per-run inventory directory under
`.output/provisioning/<runid>/`.  The directory is the on-disk record that makes
`apply` resumable and `destroy` clean: a partial apply that crashed halfway through
can be reattempted later from the same `runid`, and `destroy` reads the same
directory to know exactly what to tear down.

This spec defines the directory layout, file contents, write semantics, and the
resumability and destroy contracts that the lifecycle layer depends on.

---

## Requirements

### Requirement 1: Run Directory Layout

**User Story:** As a framework user, I want a predictable directory per run.

#### Acceptance Criteria

1. THE SYSTEM SHALL create `.output/provisioning/<runid>/` on first stage entry of
   any pipeline run.
2. THE SYSTEM SHALL write the following files inside that directory:
   - `spec.yaml` — normalised input spec.
   - `plan.yaml` — `PipelinePlan`.
   - `result.yaml` — `Dict[venue_name, ProvisioningResult]`, updated atomically
     after each stage.
   - `inventory.yaml` — full `Dict[venue_name, List[ProvisionedResource]]`.
   - `landscape.yaml` — block consumable by `automojo-landscaping` (see
     [landscape-inventory-emit](../landscape-inventory-emit/design.md)).
   - `stages.log` — per-stage entry/exit/duration records.
3. WHEN any of the YAML files is written THE SYSTEM SHALL write to a `.tmp` file
   then atomically rename to the final path, so a crash never leaves a partial
   file.

---

### Requirement 2: Resumable Apply

**User Story:** As a CI operator whose apply died mid-flight, I want to resume.

#### Acceptance Criteria

1. WHEN `apply(aspects)` is called with `aspects.runid` set to an existing run THE
   SYSTEM SHALL load `result.yaml` and `inventory.yaml` from that directory.
2. THE SYSTEM SHALL re-run every stage from `LOAD_VALIDATE` forward — the per-stage
   idempotence contract is what makes resumption safe; the engine does not
   "skip ahead" to where it stopped.
3. WHEN a resource id present in `inventory.yaml` is no longer present in the venue
   (manual deletion) THE SYSTEM SHALL log a warning and proceed; the next
   match-then-act read will recreate it.

---

### Requirement 3: Destroy Reads State

**User Story:** As a CI operator, I want destroy to use the exact inventory the
matching apply produced.

#### Acceptance Criteria

1. WHEN `destroy(aspects)` is called with `aspects.runid` set THE SYSTEM SHALL load
   `inventory.yaml` from that runid and pass the resources to each venue
   provisioner's `destroy`.
2. WHEN `runid` is not provided THE SYSTEM SHALL refuse to run and raise
   `SemanticError` (per-spec destroy without runid is too dangerous).
3. WHEN `inventory.yaml` references a resource that no longer exists in the venue
   THE SYSTEM SHALL log and continue (idempotent destroy).
4. WHEN destroy completes successfully THE SYSTEM SHALL rename the directory to
   `.output/provisioning/<runid>.destroyed/` so it remains for audit without
   being picked up as an active run.

---

### Requirement 4: Run Index

**User Story:** As a CI operator, I want to list past runs quickly.

#### Acceptance Criteria

1. THE SYSTEM SHALL maintain `.output/provisioning/index.yaml` with one entry per
   run: `{runid, started, status, spec_path, venues}`.
2. WHEN a run finishes (success or failure) THE SYSTEM SHALL append its terminal
   status to the index entry.
3. THE SYSTEM SHALL expose `list_runs() -> List[RunIndexEntry]` and
   `latest_run() -> Optional[RunIndexEntry]`.

---

### Requirement 5: Concurrency and Locking

**User Story:** As a framework author, I want concurrent runs on the same machine to
fail loudly rather than corrupt the index.

#### Acceptance Criteria

1. WHEN a run starts THE SYSTEM SHALL acquire a file lock on
   `.output/provisioning/index.yaml.lock`.
2. WHEN another run holds the lock THE SYSTEM SHALL wait up to the
   `aspects.lock_timeout_seconds` and then raise `ProvisioningLockTimeoutError`.
3. THE SYSTEM SHALL release the lock on every exit path (success, failure, signal).

---

### Requirement 6: Sensitive Data Handling

**User Story:** As a security-conscious user, I want secrets out of the persisted
state.

#### Acceptance Criteria

1. WHEN writing `spec.yaml` THE SYSTEM SHALL replace every credential reference
   with the credential vault name only — never the secret value.
2. WHEN writing `inventory.yaml` THE SYSTEM SHALL omit fields tagged `sensitive`
   in the model.
3. WHEN writing `stages.log` THE SYSTEM SHALL never log auth keys, OAuth tokens, or
   API tokens; references are by fingerprint only.
