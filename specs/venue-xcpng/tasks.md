# Tasks — XCP-ng / XenServer Provisioner

## Scaffolding

- [x] 1. Create `provisioning/venues/xcpng/` tree per `design.md`.
- [x] 2. Add `codecraftai-interop-xen` dep.
- [x] 3. Declare `XenValidationError`, `XenConflictError`,
  `ConfirmationRequiredError` in `xenerrors.py`.

## Resolver and Translator

- [x] 4. Implement `XenResolver.image_to_template_ref(family, version, arch)`.
- [x] 5. Implement `XenResolver.size_to_hardware(size_hint)`.
- [x] 6. Implement `XenResolver.pick_sr(required_gb, pool)`.
- [x] 7. Implement `XenTagTranslator.to_xen(neutral_tags, run_id)` writing
  `other_config` + `tags`, and `from_xen(vm_record)` with round-trip identity.

## Validate / Plan / Apply / Destroy / Inventory

- [x] 8. Implement `XcpngCloudProvisioner.validate(spec, aspects)` rejecting
  unsupported kinds.
- [x] 9. Implement `XenPlanBuilder.plan(spec, aspects)`.
- [x] 10. Implement `XenApplyStages.apply_networks_and_sr_validation`.
- [x] 11. Implement `XenApplyStages.apply_vms` (clone, set hardware, attach
  VDIs, push cloud-init via xenstore, start).
- [x] 12. Implement `XenCloudInitRenderer.render(spec_vm, vpn_join)`.
- [x] 13. Implement `XenDestroyStages.destroy(spec, aspects)` reversing apply,
  calling `IVPNControlPlane.delete_device` after VM destroy.
- [x] 14. Implement `XenInventory.list_run(spec, aspects)` using XenTools
  IP reporting.
- [x] 15. Persist inventory under
  `.output/provisioning/<runid>/xcpng-inventory.json`.

## Property tests (hypothesis)

- [x] 16. `test_apply_idempotent`.
- [x] 17. `test_destroy_is_inverse_of_apply`.
- [x] 18. `test_tag_round_trip_identity`.
- [x] 19. `test_validate_rejects_unsupported_kinds`.

## Integration tests (gated)

- [ ] 20. `RUN_LIVE_XCPNG=1` end-to-end against a homelab pool. (deferred: live-integration end-to-end test gated on real hardware/account)

## Documentation

- [ ] 21. Author `provisioning/venues/xcpng/README.md` cross-linking the (deferred: README.md not yet authored)
  resource model, lifecycle, vpn-join, and the Xen interop client.
