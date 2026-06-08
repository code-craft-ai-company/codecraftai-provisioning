# Implementation Plan — Landscape Inventory Emit

## Module Skeleton

- [x] 1. Create `landscapeemitter.py`
- [x] 2. Create `deviceaddressblock.py`
- [x] 3. Create `overlayaddressresolver.py`

## Emit Logic

- [x] 4. Walk inventory, filter `kind == "instance"`
- [x] 5. Build `DeviceAddressBlock` from instance attributes
- [x] 6. Omit (don't null) `public` when `public_ip=False`
- [x] 7. Resolve overlay via `IVPNControlPlane.list_devices` with per-emit cache
- [x] 8. On overlay failure, log warning and continue
- [x] 9. Preserve tags from `ProvisionedResource`
- [x] 10. Preserve group membership from spec
- [x] 11. Emit `venue` name per device entry
- [x] 12. Emit top-level `vpn:` block when any `vpn_join` is present
- [x] 13. Emit top-level `venues:` block

## Integration

- [x] 14. Wire emitter into engine `EMIT_LANDSCAPE_INVENTORY` stage
- [x] 15. Write `landscape.yaml` via atomic-write helper
- [x] 16. Run emit even on partial apply (best-effort)

## Tests

- [x] 17. `test_emit_simple_instance`
- [x] 18. `test_emit_omits_public_when_no_public_ip`
- [x] 19. `test_emit_includes_overlay_for_vpn_join_instance`
- [x] 20. `test_emit_handles_overlay_query_failure`
- [x] 21. `test_emit_preserves_tags_and_group_membership`
- [x] 22. `test_emit_empty_inventory_produces_valid_file`
- [x] 23. `test_emit_caches_list_devices_per_provider`
- [x] 24. `test_emit_includes_vpn_block_only_when_needed`
- [x] 25. `test_emit_roundtrips_through_landscape_loader_stub`

## Documentation

- [x] 26. Cross-link `codecraftai-landscaping/specs/landscape-yaml-schema` (target schema)
- [x] 27. Document the partial-apply behaviour in the module docstring
