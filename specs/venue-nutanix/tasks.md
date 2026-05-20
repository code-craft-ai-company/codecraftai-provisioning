# Tasks — Nutanix AHV Provisioner

## Scaffolding

- [ ] 1. Create `provisioning/venues/nutanix/` tree per `design.md`.
- [ ] 2. Add `automojo-interop-nutanix` dep.
- [ ] 3. Declare `NtxValidationError`, `NtxConflictError`,
  `ConfirmationRequiredError` in `ntxerrors.py`.

## Resolver and Translator

- [ ] 4. Implement `NtxResolver.image_to_uuid(family, version, arch)`.
- [ ] 5. Implement `NtxResolver.size_to_hardware(size_hint)`.
- [ ] 6. Implement `NtxResolver.pick_cluster(spec_hint, available_clusters)`.
- [ ] 7. Implement `NtxCategoryTranslator.ensure(neutral_tags, run_id)` /
  `read(vm_spec)` with round-trip identity.

## Validate / Plan / Apply / Destroy / Inventory

- [ ] 8. Implement `NutanixCloudProvisioner.validate(spec, aspects)` rejecting
  unsupported kinds and absent Objects configuration when buckets are
  requested.
- [ ] 9. Implement `NtxPlanBuilder.plan(spec, aspects)`.
- [ ] 10. Implement `NtxApplyStages.apply_network_and_flow_policies`.
- [ ] 11. Implement `NtxApplyStages.apply_vms` including base64 user_data
  rendering for `vpn_join`.
- [ ] 12. Implement the task poll loop with `aspects.timeout_seconds`.
- [ ] 13. Implement `NtxDestroyStages.destroy(spec, aspects)` reversing apply,
  calling `IVPNControlPlane.delete_device` after VM delete.
- [ ] 14. Implement `NtxInventory.list_run(spec, aspects)` using NGT IPs.
- [ ] 15. Persist inventory under
  `.output/provisioning/<runid>/nutanix-inventory.json`.

## Property tests (hypothesis)

- [ ] 16. `test_apply_idempotent`.
- [ ] 17. `test_destroy_is_inverse_of_apply`.
- [ ] 18. `test_category_value_round_trip_identity`.
- [ ] 19. `test_task_poll_honours_timeout_aspect`.
- [ ] 20. `test_validate_rejects_unsupported_kinds`.

## Integration tests (gated)

- [ ] 21. `RUN_LIVE_NUTANIX=1` end-to-end against a homelab Prism Central.

## Documentation

- [ ] 22. Author `provisioning/venues/nutanix/README.md` cross-linking the
  resource model, lifecycle, vpn-join, and the Nutanix interop client.
