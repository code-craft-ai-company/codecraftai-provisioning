# Tasks — Crusoe Cloud Provisioner

## Scaffolding

- [ ] 1. Create `provisioning/venues/crusoe/` tree per `design.md`.
- [ ] 2. Add `automojo-interop-crusoe` dep.
- [ ] 3. Declare `CrusoeValidationError`, `CrusoeConflictError`,
  `ConfirmationRequiredError` in `crusoeerrors.py`.

## Resolver and Translator

- [ ] 4. Implement `CrusoeResolver.image_to_alias(family, version, arch)`.
- [ ] 5. Implement `CrusoeResolver.size_to_instance_type(size_hint,
  accelerators, interconnect)`.
- [ ] 6. Implement `CrusoeLabelTranslator.to_crusoe(neutral_tags)` /
  `from_crusoe(d)` with round-trip identity.

## Validate / Plan / Apply / Destroy / Inventory

- [ ] 7. Implement `CrusoeCloudProvisioner.validate(spec, aspects)` rejecting
  bucket/LB asks and shared-FS provision path.
- [ ] 8. Validate that IB-requesting instance types match the interconnect
  request.
- [ ] 9. Implement `CrusoePlanBuilder.plan(spec, aspects)`.
- [ ] 10. Implement `CrusoeApplyStages.apply_network_and_firewall`.
- [ ] 11. Implement `CrusoeIbPartition.ensure_and_attach(spec, aspects)` for
  IB-grouped instances.
- [ ] 12. Implement `CrusoeApplyStages.apply_instances_and_disks` with
  `user_data` rendering.
- [ ] 13. Implement `CrusoeDestroyStages.destroy(spec, aspects)` reversing
  apply, calling `IVPNControlPlane.delete_device` after instance terminate.
- [ ] 14. Implement `CrusoeInventory.list_run(spec, aspects)`.
- [ ] 15. Persist inventory under
  `.output/provisioning/<runid>/crusoe-inventory.json`.

## Property tests (hypothesis)

- [ ] 16. `test_apply_idempotent`.
- [ ] 17. `test_destroy_is_inverse_of_apply`.
- [ ] 18. `test_label_round_trip_identity_for_conformant_inputs`.
- [ ] 19. `test_ib_partition_grouping`.
- [ ] 20. `test_validate_rejects_bucket_lb_and_fs_provision`.

## Integration tests (gated)

- [ ] 21. `RUN_LIVE_CRUSOE=1` end-to-end against a sandbox project.

## Documentation

- [ ] 22. Author `provisioning/venues/crusoe/README.md` cross-linking the
  resource model, lifecycle, vpn-join, and the Crusoe interop client.
