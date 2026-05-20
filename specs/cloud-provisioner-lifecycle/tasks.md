# Implementation Plan — Cloud Provisioner Lifecycle

## Dataclasses

- [x] 1. Create `plannedactionintent.py` — enum CREATE/UPDATE/SKIP/DELETE
- [x] 2. Create `plannedaction.py` — `PlannedAction(SchemaObject)`
- [x] 3. Create `provisioningplan.py` — `ProvisioningPlan(SchemaObject)`
- [x] 4. Create `provisionedresource.py` — `ProvisionedResource(SchemaObject)`
- [x] 5. Create `provisioningresult.py` — `ProvisioningResult(SchemaObject)`

## Abstract Base

- [x] 6. Flesh out `cloudprovisioner.py` from the current stub
- [x] 7. Define `OWNER_TAG_KEY` / `OWNER_TAG_VALUE` class constants
- [x] 8. Declare 5 abstract methods with named-only `aspects` parameter
- [x] 9. Implement `_destroy_order(plan)` helper
- [x] 10. Implement `_planned_action_for(...)` helper
- [x] 11. Implement confirm-gating wrapper for `destroy`
- [x] 12. Raise `SemanticError` when `aspects.confirm is False` and destroy invoked

## Match-then-Act Helpers

- [x] 13. Document the `_ensure_<kind>` pattern in base-class docstring
- [x] 14. Provide example `_ensure_<kind>` template in module-level comment
- [x] 15. Define `_read_by_tag` contract used by subclasses for idempotency reads

## FakeCloudProvisioner

- [x] 16. Create `_fake/fakecloudprovisioner.py`
- [x] 17. Implement in-memory venue dict
- [x] 18. Implement validate using model semantic checks
- [x] 19. Implement plan via diff against in-memory state
- [x] 20. Implement apply with match-then-act on the dict
- [x] 21. Implement destroy honouring confirm
- [x] 22. Implement inventory returning dict values

## Tests — Examples

- [x] 23. `test_planned_action_roundtrip`
- [x] 24. `test_provisioning_plan_roundtrip`
- [x] 25. `test_provisioned_resource_roundtrip`
- [x] 26. `test_destroy_without_confirm_raises_semantic_error`
- [x] 27. `test_fake_apply_creates_resources`
- [x] 28. `test_fake_inventory_lists_owned_resources_only`
- [x] 29. `test_fake_plan_marks_existing_as_skip`

## Tests — Property (hypothesis) ⊙

- [x] 30. `test_property_apply_idempotence`
- [x] 31. `test_property_destroy_inversibility`
- [x] 32. `test_property_plan_stability`
- [x] 33. `test_property_owner_tag_invariant`

## Documentation

- [x] 34. Document §5 idempotency-budget decision in module docstring
- [x] 35. Cross-link `provisioning-engine-pipeline` for stage ordering
