# Implementation Plan — Provisioning State Persistence

## Helpers

- [x] 1. Create `atomicwrite.py` — `write_tmp_then_rename`
- [x] 2. Create `crossplatformlock.py` — POSIX `flock` / Windows `msvcrt`
- [x] 3. Create `redactforpersistence.py` — secret scrubber

## State Types

- [x] 4. Create `runstatus.py` — enum STARTED/APPLIED/FAILED/DESTROYED
- [x] 5. Create `runindexentry.py` — `RunIndexEntry(SchemaObject)`
- [x] 6. Create `runstate.py` — `RunState(SchemaObject)`

## Store Class

- [x] 7. Create `provisioningstatestore.py`
- [x] 8. Implement `create_run(runid, spec_path, venues) -> Path`
- [x] 9. Implement `load_run(runid) -> RunState`
- [x] 10. Implement `write_state(runid, state)` using atomic write
- [x] 11. Implement `append_log(runid, line)`
- [x] 12. Implement `list_runs() -> List[RunIndexEntry]`
- [x] 13. Implement `latest_run() -> Optional[RunIndexEntry]`
- [x] 14. Implement `mark_destroyed(runid)` — rename dir

## Engine Integration

- [x] 15. Engine creates run dir on entry
- [x] 16. Engine writes spec/plan/result/inventory after each stage
- [x] 17. Engine acquires + releases index lock around the whole run
- [x] 18. Engine refuses destroy without `aspects.runid`
- [x] 19. Engine logs each stage entry/exit/duration to `stages.log`

## Redaction

- [x] 20. Mark sensitive `SchemaField` definitions in model classes
- [x] 21. Apply redactor before serialising any state file
- [x] 22. Verify no auth-key value ever reaches disk

## Tests

- [x] 23. `test_write_tmp_then_rename_atomic`
- [x] 24. `test_create_run_dir_layout`
- [x] 25. `test_load_run_roundtrips_state`
- [x] 26. `test_resume_with_existing_runid`
- [x] 27. `test_destroy_reads_inventory_yaml`
- [x] 28. `test_destroy_without_runid_raises_semantic_error`
- [x] 29. `test_mark_destroyed_renames_dir`
- [x] 30. `test_lock_contention_times_out`
- [x] 31. `test_secret_scrubbed_from_persisted_spec`
- [x] 32. `test_run_index_appended_on_each_run`
