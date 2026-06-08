# Tasks — Crusoe Cloud Provisioner

## Scaffolding

- [x] 1. Create `provisioning/venues/crusoe/` tree per `design.md`.
- [x] 2. Add `codecraftai-interop-crusoe` dep.
- [x] 3. Declare `CrusoeValidationError`, `CrusoeConflictError`,
  `ConfirmationRequiredError` in `crusoeerrors.py`.

## Resolver and Translator

- [x] 4. Implement `CrusoeResolver.image_to_alias(family, version, arch)`.
- [x] 5. Implement `CrusoeResolver.size_to_instance_type(size_hint,
  accelerators, interconnect)`.
- [x] 6. Implement `CrusoeLabelTranslator.to_crusoe(neutral_tags)` /
  `from_crusoe(d)` with round-trip identity.

## Validate / Plan / Apply / Destroy / Inventory

- [x] 7. Implement `CrusoeCloudProvisioner.validate(spec, aspects)` rejecting
  bucket/LB asks and shared-FS provision path.
- [x] 8. Validate that IB-requesting instance types match the interconnect
  request.
- [x] 9. Implement `CrusoePlanBuilder.plan(spec, aspects)`.
- [x] 10. Implement `CrusoeApplyStages.apply_network_and_firewall`.
- [x] 11. Implement `CrusoeIbPartition.ensure_and_attach(spec, aspects)` for
  IB-grouped instances.
- [x] 12. Implement `CrusoeApplyStages.apply_instances_and_disks` with
  `user_data` rendering.
- [x] 13. Implement `CrusoeDestroyStages.destroy(spec, aspects)` reversing
  apply, calling `IVPNControlPlane.delete_device` after instance terminate.
- [x] 14. Implement `CrusoeInventory.list_run(spec, aspects)`.
- [x] 15. Persist inventory under
  `.output/provisioning/<runid>/crusoe-inventory.json`.

## Property tests (hypothesis)

- [x] 16. `test_apply_idempotent`.
- [x] 17. `test_destroy_is_inverse_of_apply`.
- [x] 18. `test_label_round_trip_identity_for_conformant_inputs`.
- [x] 19. `test_ib_partition_grouping`.
- [x] 20. `test_validate_rejects_bucket_lb_and_fs_provision`.

## Integration tests (gated)

- [ ] 21. `RUN_LIVE_CRUSOE=1` end-to-end against a sandbox project. (deferred: live-integration end-to-end test gated on real hardware/account)

## Documentation

- [x] 22. Author `provisioning/venues/crusoe/README.md` cross-linking the
  resource model, lifecycle, vpn-join, and the Crusoe interop client.
