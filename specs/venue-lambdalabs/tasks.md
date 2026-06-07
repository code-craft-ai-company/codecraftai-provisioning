# Tasks — Lambda Labs Provisioner

## Scaffolding

- [x] 1. Create `provisioning/venues/lambdalabs/` tree per `design.md`.
- [x] 2. Add `codecraftai-interop-lambdalabs` dep.
- [x] 3. Declare `LlValidationError`, `LlCapacityError`,
  `ConfirmationRequiredError` in `llerrors.py`.

## Resolver and Translator

- [x] 4. Implement `LlResolver.accelerator_to_instance_type(accel_spec,
  interconnect)` returning either a single-instance SKU or a 1-Click Cluster
  product code.
- [x] 5. Implement `LlSidecarTag.write(neutral_tags, instance_id)` and
  `read(instance_id)` with round-trip identity.

## Validate / Plan / Apply / Destroy / Inventory

- [x] 6. Implement `LambdalabsCloudProvisioner.validate(spec, aspects)`
  rejecting bucket/LB/DNS and warning on unsupported network resources.
- [x] 7. Implement `LlPlanBuilder.plan(spec, aspects)`.
- [x] 8. Implement `LlApplyStages.ensure_ssh_keys`.
- [x] 9. Implement `LlApplyStages.apply_instances` covering both single
  Instance and 1-Click Cluster branches with `user_data` rendering.
- [x] 10. Implement `LlDestroyStages.destroy(spec, aspects)`, calling
  `IVPNControlPlane.delete_device` after terminate.
- [x] 11. Implement `LlInventory.list_run(spec, aspects)`.
- [x] 12. Persist sidecar tags under
  `.output/provisioning/<runid>/lambdalabs-tags.json` and inventory under
  `.output/provisioning/<runid>/lambdalabs-inventory.json`.

## Property tests (hypothesis)

- [x] 13. `test_apply_idempotent`.
- [x] 14. `test_destroy_is_inverse_of_apply`.
- [x] 15. `test_sidecar_tag_round_trip_identity`.
- [x] 16. `test_one_click_vs_single_instance_branch`.
- [x] 17. `test_validate_rejects_bucket_lb_dns`.

## Integration tests (gated)

- [ ] 18. `RUN_LIVE_LAMBDA=1` end-to-end against a sandbox account (incurs (deferred: live-integration end-to-end test gated on real hardware/account)
  per-second GPU charges; excluded from PR CI).

## Documentation

- [ ] 19. Author `provisioning/venues/lambdalabs/README.md` cross-linking the (deferred: README.md not yet authored)
  resource model, lifecycle, vpn-join, and the Lambda Labs interop client.
