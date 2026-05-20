# Implementation Plan — Provisioning Engine Pipeline

## Engine Skeleton

- [x] 1. Replace `provisioningengine.py` stub with full class
- [x] 2. Create `pipelinestage.py` — enum with 8 stages
- [x] 3. Create `pipelinespec.py` — typed parsed spec
- [x] 4. Create `pipelineplan.py` — aggregate plan record
- [x] 5. Implement `from_spec_file(path)` classmethod
- [x] 6. Generate per-run UUID and create `.output/provisioning/<runid>/`

## Dependency Graph

- [x] 7. Create `dependencygraph.py`
- [x] 8. Build edges per documented dependency rules
- [x] 9. Implement Kahn's algorithm topo-sort with alphabetical tiebreaker
- [x] 10. Detect cycles and raise `SchemaSemanticError` listing members

## Stage Modules

- [x] 11. Create `stages/loadvalidate.py`
- [x] 12. Create `stages/planstage.py`
- [x] 13. Create `stages/applynetworkingstage.py`
- [x] 14. Create `stages/applycomputestage.py`
- [x] 15. Create `stages/applydnsstoragelbstage.py`
- [x] 16. Create `stages/bootstrapvpnstage.py`
- [x] 17. Create `stages/verifystage.py`
- [x] 18. Create `stages/emitlandscapeinventorystage.py`

## Provisioner Subset Helper

- [x] 19. Add `apply_subset(kinds, aspects)` to `CloudProvisioner` base
- [x] 20. Preserve topological order within the subset

## Aspects Wiring

- [x] 21. Define `ProvisioningAspects` with `dry_run`, `confirm`, `verify_timeout`
- [x] 22. Per-stage entry/exit/duration logging keyed by `runid`
- [x] 23. Halt on first exception; never swallow

## Destroy Path

- [x] 24. Implement reverse stage order
- [x] 25. Within each stage, reverse the topo order
- [x] 26. Require `aspects.confirm=True` or raise `SemanticError`

## Tests — Examples

- [x] 27. `test_engine_loads_spec_into_typed_pipelinespec`
- [x] 28. `test_validate_invokes_each_provisioner_validate`
- [x] 29. `test_plan_aggregates_per_venue_plans`
- [x] 30. `test_apply_runs_stages_in_documented_order`
- [x] 31. `test_dry_run_skips_apply_stages`
- [x] 32. `test_verify_polls_until_running`
- [x] 33. `test_destroy_requires_confirm`
- [x] 34. `test_destroy_reverses_stage_and_topo_order`

## Tests — Property (hypothesis) ⊙

- [x] 35. `test_property_instance_applied_after_subnet`
- [x] 36. `test_property_dns_applied_after_referenced_instance`
- [x] 37. `test_property_topo_sort_stable`
- [x] 38. `test_property_cycle_raises_semantic_error_only`

## Documentation

- [x] 39. Document the 8-stage contract in module docstring
- [x] 40. Cross-link `provisioning-state-persistence`
