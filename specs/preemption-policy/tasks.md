# Implementation Plan — Preemption Policy

## Enum and Errors

- [x] 1. Create `preemptionpolicy.py` — enum with 3 values
- [ ] 2. Create `preemptionerrors.py` — `ProvisioningPreemptionError`
- [ ] 3. Create `preemptionevent.py` — `PreemptionEvent(SchemaObject)`

## CloudInstance Field

- [x] 4. Add `preemption_policy` field to `CloudInstance` with default `FAIL`
- [x] 5. Validate literal membership at construction
- [x] 6. Round-trip through `to_dict / from_dict`

## Handler

- [ ] 7. Create `preemptionhandler.py` with `handle_preemption(...)`
- [ ] 8. Implement FAIL branch — raise `ProvisioningPreemptionError`
- [ ] 9. Implement REACQUIRE branch — create new instance with same spec
- [ ] 10. Implement BEST_EFFORT branch — log + return None
- [ ] 11. Log structured event for every preemption decision

## Engine Integration

- [ ] 12. Call handler from `apply` match-then-act when venue_id missing
- [ ] 13. Call handler from `verify` when instance terminated mid-poll
- [ ] 14. Refresh ephemeral auth key on REACQUIRE
- [ ] 15. Re-run cloud-init renderer for REACQUIRE replacement

## Venue Capability

- [ ] 16. Add `supports_preemption() -> bool` classmethod to base provisioner
- [ ] 17. Default `False`; override to `True` on AWS/Azure/GCP/Oracle/LambdaLabs

## Landscape Emit

- [ ] 18. Include `preemption_policy` on each emitted device entry

## Tests

- [x] 19. `test_default_policy_is_fail`
- [x] 20. `test_policy_rejects_invalid_value`
- [ ] 21. `test_fail_branch_raises_preemption_error`
- [ ] 22. `test_reacquire_branch_creates_replacement`
- [ ] 23. `test_reacquire_logs_warning_with_old_and_new_id`
- [ ] 24. `test_best_effort_branch_drops_from_inventory`
- [ ] 25. `test_destroy_during_reacquire_does_not_recreate`
- [ ] 26. `test_landscape_emit_includes_policy`
- [ ] 27. `test_supports_preemption_default_false`

## Documentation

- [ ] 28. Document §7.6 fail-loud-default rationale in module docstring
- [ ] 29. Cross-link `cloud-provisioner-lifecycle` and `provisioning-engine-pipeline`
