# Tasks — Vultr Cloud Provisioner

## Scaffolding

- [ ] 1. Create `provisioning/venues/vultr/` tree per `design.md`.
- [ ] 2. Add `automojo-interop-vultr` dep (built on
  `automojo-restclient-base`).
- [ ] 3. Declare `VultrValidationError`, `VultrConflictError`,
  `ConfirmationRequiredError` in `vultrerrors.py`.

## Resolver and Translator

- [ ] 4. Implement `VultrResolver.image_to_os_id(family, version, arch)`
  consulting `GET /os`.
- [ ] 5. Implement `VultrResolver.size_to_plan(size_hint, accelerators)`.
- [ ] 6. Implement `VultrTagTranslator.to_vultr(neutral_tags)` /
  `from_vultr(strings)` with round-trip identity.

## Validate / Plan / Apply / Destroy / Inventory

- [ ] 7. Implement `VultrCloudProvisioner.validate(spec, aspects)` rejecting
  interconnect and shared-FS asks.
- [ ] 8. Implement `VultrPlanBuilder.plan(spec, aspects)`.
- [ ] 9. Implement `VultrApplyStages.apply_network_and_firewall`.
- [ ] 10. Implement `VultrApplyStages.apply_instances_and_blocks` with
  base64 `user_data` rendering.
- [ ] 11. Implement `VultrApplyStages.apply_object_storage_and_dns`.
- [ ] 12. Implement `VultrDestroyStages.destroy(spec, aspects)` reversing
  apply, calling `IVPNControlPlane.delete_device` after Instance delete.
- [ ] 13. Implement `VultrInventory.list_run(spec, aspects)`.
- [ ] 14. Persist inventory under
  `.output/provisioning/<runid>/vultr-inventory.json`.

## Property tests (hypothesis)

- [ ] 15. `test_apply_idempotent`.
- [ ] 16. `test_destroy_is_inverse_of_apply`.
- [ ] 17. `test_tag_round_trip_identity`.
- [ ] 18. `test_validate_rejects_interconnect_and_shared_fs`.

## Integration tests (gated)

- [ ] 19. `RUN_LIVE_VULTR=1` end-to-end against a sandbox account.

## Documentation

- [ ] 20. Author `provisioning/venues/vultr/README.md` cross-linking the
  resource model, lifecycle, vpn-join, and the Vultr interop client.
