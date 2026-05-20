# Implementation Plan — Preemption Policy

## Enum and Errors

- [x] 1. Create `preemptionpolicy.py` — enum with 3 values
- [x] 2. Create `preemptionerrors.py` — `ProvisioningPreemptionError`
- [x] 3. Create `preemptionevent.py` — `PreemptionEvent(SchemaObject)`

## CloudInstance Field

- [x] 4. Add `preemption_policy` field to `CloudInstance` with default `FAIL`
- [x] 5. Validate literal membership at construction
- [x] 6. Round-trip through `to_dict / from_dict`

## Handler

- [x] 7. Create `preemptionhandler.py` with `handle_preemption(...)`
- [x] 8. Implement FAIL branch — raise `ProvisioningPreemptionError`
- [x] 9. Implement REACQUIRE branch — create new instance with same spec
- [x] 10. Implement BEST_EFFORT branch — log + return None
- [x] 11. Log structured event for every preemption decision

## Engine Integration

- [x] 12. Call handler from `apply` match-then-act when venue_id missing
        — engine `_handle_apply_preemptions` reads preemption-tagged errors
        from each apply-stage result and dispatches `handle_preemption`.
- [x] 13. Call handler from `verify` when instance terminated mid-poll
        — engine `_stage_verify` dispatches `handle_preemption` for every
        created instance found missing from a fresh inventory.
- [x] 14. Refresh ephemeral auth key on REACQUIRE
        — handler `_refresh_reacquire_inputs` invokes the provisioner's
        optional `refresh_vpn_authkey` hook before recreation.
- [x] 15. Re-run cloud-init renderer for REACQUIRE replacement
        — handler `_refresh_reacquire_inputs` invokes the provisioner's
        optional `render_cloud_init` hook before recreation.

## Venue Capability

- [x] 16. Add `supports_preemption() -> bool` classmethod to base provisioner
- [x] 17. Default `False`; override to `True` on AWS/Azure/GCP/Oracle/LambdaLabs

## Landscape Emit

- [x] 18. Include `preemption_policy` on each emitted device entry
        — `ProvisionedResource` now carries a `preemption_policy` field
        threaded through from `CloudInstance`; `LandscapeEmitter` emits it on
        every device entry, falling back to the spec then the FAIL default.

## Tests

- [x] 19. `test_default_policy_is_fail`
- [x] 20. `test_policy_rejects_invalid_value`
- [x] 21. `test_fail_branch_raises_preemption_error`
- [x] 22. `test_reacquire_branch_creates_replacement`
- [x] 23. `test_reacquire_logs_warning_with_old_and_new_id`
- [x] 24. `test_best_effort_branch_drops_from_inventory`
- [x] 25. `test_destroy_during_reacquire_does_not_recreate`
- [x] 26. `test_landscape_emit_includes_policy`
- [x] 27. `test_supports_preemption_default_false`

## Documentation

- [x] 28. Document §7.6 fail-loud-default rationale in module docstring
- [x] 29. Cross-link `cloud-provisioner-lifecycle` and `provisioning-engine-pipeline`
