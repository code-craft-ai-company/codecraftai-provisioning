# Tasks — Lambda Labs Provisioner

## Scaffolding

- [ ] 1. Create `provisioning/venues/lambdalabs/` tree per `design.md`.
- [ ] 2. Add `automojo-interop-lambdalabs` dep.
- [ ] 3. Declare `LlValidationError`, `LlCapacityError`,
  `ConfirmationRequiredError` in `llerrors.py`.

## Resolver and Translator

- [ ] 4. Implement `LlResolver.accelerator_to_instance_type(accel_spec,
  interconnect)` returning either a single-instance SKU or a 1-Click Cluster
  product code.
- [ ] 5. Implement `LlSidecarTag.write(neutral_tags, instance_id)` and
  `read(instance_id)` with round-trip identity.

## Validate / Plan / Apply / Destroy / Inventory

- [ ] 6. Implement `LambdalabsCloudProvisioner.validate(spec, aspects)`
  rejecting bucket/LB/DNS and warning on unsupported network resources.
- [ ] 7. Implement `LlPlanBuilder.plan(spec, aspects)`.
- [ ] 8. Implement `LlApplyStages.ensure_ssh_keys`.
- [ ] 9. Implement `LlApplyStages.apply_instances` covering both single
  Instance and 1-Click Cluster branches with `user_data` rendering.
- [ ] 10. Implement `LlDestroyStages.destroy(spec, aspects)`, calling
  `IVPNControlPlane.delete_device` after terminate.
- [ ] 11. Implement `LlInventory.list_run(spec, aspects)`.
- [ ] 12. Persist sidecar tags under
  `.output/provisioning/<runid>/lambdalabs-tags.json` and inventory under
  `.output/provisioning/<runid>/lambdalabs-inventory.json`.

## Property tests (hypothesis)

- [ ] 13. `test_apply_idempotent`.
- [ ] 14. `test_destroy_is_inverse_of_apply`.
- [ ] 15. `test_sidecar_tag_round_trip_identity`.
- [ ] 16. `test_one_click_vs_single_instance_branch`.
- [ ] 17. `test_validate_rejects_bucket_lb_dns`.

## Integration tests (gated)

- [ ] 18. `RUN_LIVE_LAMBDA=1` end-to-end against a sandbox account (incurs
  per-second GPU charges; excluded from PR CI).

## Documentation

- [ ] 19. Author `provisioning/venues/lambdalabs/README.md` cross-linking the
  resource model, lifecycle, vpn-join, and the Lambda Labs interop client.
