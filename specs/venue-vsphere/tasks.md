# Tasks — VSphere Provisioner

## Scaffolding

- [x] 1. Create `provisioning/venues/vsphere/` tree per `design.md`.
- [x] 2. Add `automojo-interop-vsphere` dep; gate optional
  `automojo-interop-nsx` behind an extras feature flag.
- [x] 3. Declare `VsValidationError`, `VsConflictError`,
  `VsCapacityError`, `ConfirmationRequiredError` in `vserrors.py`.

## Resolver and Translator

- [x] 4. Implement `VsResolver.image_to_library_or_template(family, version,
  arch)` returning a `LibraryItemRef` or `TemplateRef`.
- [x] 5. Implement `VsResolver.size_to_hardware(size_hint)` (CPU/RAM/disk).
- [x] 6. Implement `VsResolver.pick_datastore(required_gb, cluster_ref)` via
  `find_datastore_with_free_gb`.
- [x] 7. Implement `VsTagTranslator.to_vs(neutral_tags)` (creates Categories +
  Tags) and `from_vs(refs)` with round-trip identity.

## Validate / Plan / Apply / Destroy / Inventory

- [x] 8. Implement `VSphereCloudProvisioner.validate(spec, aspects)`
  rejecting `CloudObjectBucket`, `CloudInterconnect != NONE`, unsupported
  shared-FS kinds, and `CloudLoadBalancer` when NSX is absent.
- [x] 9. Implement `VsPlanBuilder.plan(spec, aspects)`.
- [x] 10. Implement `VsApplyStages.apply_networking` (DVS + Port Groups).
- [x] 11. Implement `VsApplyStages.apply_vms` choosing
  `Content.OvfLibraryItem.deploy` for library-backed images and
  `Vm.create` (VmCreateSpec) otherwise.
- [x] 12. Implement `VsApplyStages.apply_disks_and_customisation` including
  `VsGuestCustomRenderer` for cloud-init/sysprep with `vpn_join` injection.
- [x] 13. Await every async op via `TaskHandle.wait(aspects=aspects)`.
- [x] 14. Implement `VsDestroyStages.destroy(spec, aspects)` reversing apply
  (power-off → delete VM → delete port group), calling
  `IVPNControlPlane.delete_device` after VM delete.
- [x] 15. Implement `VsInventory.list_run(spec, aspects)`.
- [x] 16. Persist inventory under
  `.output/provisioning/<runid>/vsphere-inventory.json`.

## Property tests (hypothesis)

- [x] 17. `test_apply_idempotent`.
- [x] 18. `test_destroy_is_inverse_of_apply`.
- [x] 19. `test_category_tag_round_trip_identity`.
- [x] 20. `test_validate_rejects_object_bucket_and_interconnect`.
- [x] 21. `test_validate_rejects_lb_without_nsx`.
- [x] 22. `test_library_vs_template_fallback`.

## Integration tests (gated)

- [ ] 23. `RUN_LIVE_VSPHERE=1` end-to-end against a homelab vCenter. (deferred: live-integration end-to-end test gated on real hardware/account)

## Documentation

- [x] 24. Author `provisioning/venues/vsphere/README.md` cross-linking the
  resource model, lifecycle, vpn-join, and the vSphere interop client spec.
