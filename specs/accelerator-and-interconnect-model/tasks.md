# Implementation Plan — Accelerator and Interconnect Model

## Model Classes

- [x] 1. Create `cloudacceleratorspec.py` — kind/model/count/interconnect/memory_gb
- [x] 2. Create `cloudinterconnect.py` — kind/bandwidth_gbps/topology
- [x] 3. Create `sharedfsmountspec.py` — filesystem_name/target_instance/mount_path/options
- [x] 4. Create `cloudsharedfilesystem.py` — attach-or-provision discriminator on `existing_id`

## CloudInstance Extension

- [x] 5. Add optional `accelerators` field to `CloudInstance`
- [x] 6. Add optional `interconnect` field to `CloudInstance`
- [x] 7. Add optional `placement_group` field to `CloudInstance`
- [x] 8. Add optional `shared_fs_mounts` field to `CloudInstance`
- [x] 9. Verify baseline (no optional fields set) round-trips identically

## Validation

- [x] 10. Validate `count > 0` and `bandwidth_gbps > 0` at construction
- [x] 11. Validate `mount_path` starts with `/` and is non-empty
- [x] 12. Validate `existing_id XOR size_tb` for shared FS
- [ ] 13. Add venue-capability stub function used by lifecycle `validate`
- [ ] 14. Emit warning when `interconnect` set but `placement_group` is None
- [ ] 15. Emit warning when `vpn_join` and training-fabric `interconnect` co-occur

## Tests — Examples

- [x] 16. `test_accelerator_spec_roundtrip`
- [x] 17. `test_accelerator_spec_rejects_zero_count`
- [x] 18. `test_interconnect_roundtrip_for_every_kind`
- [x] 19. `test_shared_fs_attach_only_when_existing_id_set`
- [x] 20. `test_shared_fs_rejects_no_size_no_existing_id`
- [x] 21. `test_mount_spec_rejects_relative_path`
- [x] 22. `test_cloudinstance_baseline_unchanged`
- [ ] 23. `test_cloudinstance_with_accelerators_roundtrip`
- [ ] 24. `test_mount_target_resolution_during_validate`
- [ ] 25. `test_vpn_join_plus_training_fabric_warns`

## Documentation

- [ ] 26. Document the v1 attach-only constraint for shared FS in module docstring
- [ ] 27. Cross-link `accelerator-catalog` from `CloudAcceleratorSpec` docstring
