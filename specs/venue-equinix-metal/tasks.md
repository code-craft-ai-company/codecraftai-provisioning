# Tasks — Equinix Metal Provisioner

## Scaffolding

- [x] 1. Create `provisioning/venues/equinix/` tree per `design.md`.
- [ ] 2. Add `automojo-interop-equinix-metal` + `packet-python` deps. (deferred: cross-repo dependency wiring owned by package packaging step)
- [x] 3. Declare `MetalValidationError`, `MetalConflictError`,
  `ConfirmationRequiredError` in `metalerrors.py`.

## Resolver and Translator

- [x] 4. Implement `MetalResolver.image_to_os_slug(family, version, arch)`.
- [x] 5. Implement `MetalResolver.size_to_plan(size_hint, accelerators, metro)`
  honouring per-metro plan availability.
- [x] 6. Implement `MetalTagTranslator.to_metal(neutral_tags)` /
  `from_metal(strings)` with round-trip identity.

## Validate / Plan / Apply / Destroy / Inventory

- [x] 7. Implement `EquinixMetalCloudProvisioner.validate(spec, aspects)`
  rejecting `CloudObjectBucket`, `CloudInterconnect != NONE`, shared-FS, and
  LB asks.
- [x] 8. Implement `MetalPlanBuilder.plan(spec, aspects)`.
- [x] 9. Implement `MetalApplyStages.apply_network` (VLAN + IP reservations).
- [x] 10. Implement `MetalApplyStages.apply_devices` with `userdata`
  rendering for `vpn_join`.
- [x] 11. Implement `MetalDestroyStages.destroy(spec, aspects)` reversing
  apply, calling `IVPNControlPlane.delete_device` after Device delete.
- [x] 12. Implement `MetalInventory.list_run(spec, aspects)`.
- [x] 13. Persist inventory under
  `.output/provisioning/<runid>/metal-inventory.json`.

## Property tests (hypothesis)

- [x] 14. `test_apply_idempotent`.
- [x] 15. `test_destroy_is_inverse_of_apply`.
- [x] 16. `test_tag_round_trip_identity`.
- [x] 17. `test_validate_rejects_unsupported_kinds`.

## Integration tests (gated)

- [ ] 18. `RUN_LIVE_METAL=1` end-to-end against a sandbox project (long (deferred: live-integration end-to-end test gated on real hardware/account)
  runtime; not on PR CI).

## Documentation

- [ ] 19. Author `provisioning/venues/equinix/README.md` cross-linking the (deferred: README.md not yet authored)
  resource model, lifecycle, vpn-join, and the Metal interop client.
