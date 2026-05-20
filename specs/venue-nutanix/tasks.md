# Tasks — Nutanix AHV Provisioner

## Scaffolding

- [x] 1. Create `provisioning/venues/nutanix/` tree per `design.md`.
- [x] 2. Add `automojo-interop-nutanix` dep.
- [x] 3. Declare `NtxValidationError`, `NtxConflictError`,
  `ConfirmationRequiredError` in `ntxerrors.py`.

## Resolver and Translator

- [x] 4. Implement `NtxResolver.image_to_uuid(family, version, arch)`.
- [x] 5. Implement `NtxResolver.size_to_hardware(size_hint)`.
- [x] 6. Implement `NtxResolver.pick_cluster(spec_hint, available_clusters)`.
- [x] 7. Implement `NtxCategoryTranslator.ensure(neutral_tags, run_id)` /
  `read(vm_spec)` with round-trip identity.

## Validate / Plan / Apply / Destroy / Inventory

- [x] 8. Implement `NutanixCloudProvisioner.validate(spec, aspects)` rejecting
  unsupported kinds and absent Objects configuration when buckets are
  requested.
- [x] 9. Implement `NtxPlanBuilder.plan(spec, aspects)`.
- [x] 10. Implement `NtxApplyStages.apply_network_and_flow_policies`.
- [x] 11. Implement `NtxApplyStages.apply_vms` including base64 user_data
  rendering for `vpn_join`.
- [x] 12. Implement the task poll loop with `aspects.timeout_seconds`.
- [x] 13. Implement `NtxDestroyStages.destroy(spec, aspects)` reversing apply,
  calling `IVPNControlPlane.delete_device` after VM delete.
- [x] 14. Implement `NtxInventory.list_run(spec, aspects)` using NGT IPs.
- [x] 15. Persist inventory under
  `.output/provisioning/<runid>/nutanix-inventory.json`.

## Property tests (hypothesis)

- [x] 16. `test_apply_idempotent`.
- [x] 17. `test_destroy_is_inverse_of_apply`.
- [x] 18. `test_category_value_round_trip_identity`.
- [x] 19. `test_task_poll_honours_timeout_aspect`.
- [x] 20. `test_validate_rejects_unsupported_kinds`.

## Integration tests (gated)

- [ ] 21. `RUN_LIVE_NUTANIX=1` end-to-end against a homelab Prism Central.

## Documentation

- [x] 22. Author `provisioning/venues/nutanix/README.md` cross-linking the
  resource model, lifecycle, vpn-join, and the Nutanix interop client.
