# Tasks — Linode Cloud Provisioner

## Scaffolding

- [x] 1. Create `provisioning/venues/linode/` tree per `design.md`.
- [ ] 2. Add `automojo-interop-linode` + `linode_api4` deps. (deferred: cross-repo dependency wiring owned by package packaging step)
- [x] 3. Declare `LinodeValidationError`, `LinodeConflictError`,
  `ConfirmationRequiredError` in `linodeerrors.py`.

## Resolver and Translator

- [x] 4. Implement `LinodeResolver.image_to_id(family, version, arch)`.
- [x] 5. Implement `LinodeResolver.size_to_type(size_hint, accelerators)`.
- [x] 6. Implement `LinodeTagTranslator.to_linode(neutral_tags)` /
  `from_linode(strings)` with round-trip identity.

## Validate / Plan / Apply / Destroy / Inventory

- [x] 7. Implement `LinodeCloudProvisioner.validate(spec, aspects)` rejecting
  interconnect and shared-FS asks.
- [x] 8. Implement `LinodePlanBuilder.plan(spec, aspects)`.
- [x] 9. Implement `LinodeApplyStages.apply_network_and_firewall`.
- [x] 10. Implement `LinodeApplyStages.apply_instances_and_volumes` with
  `metadata.user_data` rendering.
- [x] 11. Implement `LinodeApplyStages.apply_object_storage_and_dns`.
- [x] 12. Implement `LinodeDestroyStages.destroy(spec, aspects)` reversing
  apply, calling `IVPNControlPlane.delete_device` after Instance delete.
- [x] 13. Implement `LinodeInventory.list_run(spec, aspects)`.
- [x] 14. Persist inventory under
  `.output/provisioning/<runid>/linode-inventory.json`.

## Property tests (hypothesis)

- [x] 15. `test_apply_idempotent`.
- [x] 16. `test_destroy_is_inverse_of_apply`.
- [x] 17. `test_tag_round_trip_identity`.
- [x] 18. `test_validate_rejects_interconnect_and_shared_fs`.

## Integration tests (gated)

- [ ] 19. `RUN_LIVE_LINODE=1` end-to-end against a sandbox account. (deferred: live-integration end-to-end test gated on real hardware/account)

## Documentation

- [ ] 20. Author `provisioning/venues/linode/README.md` cross-linking the (deferred: README.md not yet authored)
  resource model, lifecycle, vpn-join, and the Linode interop client.
