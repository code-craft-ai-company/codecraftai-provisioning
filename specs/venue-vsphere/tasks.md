# Tasks — VSphere Provisioner

## Scaffolding

- [ ] 1. Create `provisioning/venues/vsphere/` tree per `design.md`.
- [ ] 2. Add `automojo-interop-vsphere` dep; gate optional
  `automojo-interop-nsx` behind an extras feature flag.
- [ ] 3. Declare `VsValidationError`, `VsConflictError`,
  `VsCapacityError`, `ConfirmationRequiredError` in `vserrors.py`.

## Resolver and Translator

- [ ] 4. Implement `VsResolver.image_to_library_or_template(family, version,
  arch)` returning a `LibraryItemRef` or `TemplateRef`.
- [ ] 5. Implement `VsResolver.size_to_hardware(size_hint)` (CPU/RAM/disk).
- [ ] 6. Implement `VsResolver.pick_datastore(required_gb, cluster_ref)` via
  `find_datastore_with_free_gb`.
- [ ] 7. Implement `VsTagTranslator.to_vs(neutral_tags)` (creates Categories +
  Tags) and `from_vs(refs)` with round-trip identity.

## Validate / Plan / Apply / Destroy / Inventory

- [ ] 8. Implement `VSphereCloudProvisioner.validate(spec, aspects)`
  rejecting `CloudObjectBucket`, `CloudInterconnect != NONE`, unsupported
  shared-FS kinds, and `CloudLoadBalancer` when NSX is absent.
- [ ] 9. Implement `VsPlanBuilder.plan(spec, aspects)`.
- [ ] 10. Implement `VsApplyStages.apply_networking` (DVS + Port Groups).
- [ ] 11. Implement `VsApplyStages.apply_vms` choosing
  `Content.OvfLibraryItem.deploy` for library-backed images and
  `Vm.create` (VmCreateSpec) otherwise.
- [ ] 12. Implement `VsApplyStages.apply_disks_and_customisation` including
  `VsGuestCustomRenderer` for cloud-init/sysprep with `vpn_join` injection.
- [ ] 13. Await every async op via `TaskHandle.wait(aspects=aspects)`.
- [ ] 14. Implement `VsDestroyStages.destroy(spec, aspects)` reversing apply
  (power-off → delete VM → delete port group), calling
  `IVPNControlPlane.delete_device` after VM delete.
- [ ] 15. Implement `VsInventory.list_run(spec, aspects)`.
- [ ] 16. Persist inventory under
  `.output/provisioning/<runid>/vsphere-inventory.json`.

## Property tests (hypothesis)

- [ ] 17. `test_apply_idempotent`.
- [ ] 18. `test_destroy_is_inverse_of_apply`.
- [ ] 19. `test_category_tag_round_trip_identity`.
- [ ] 20. `test_validate_rejects_object_bucket_and_interconnect`.
- [ ] 21. `test_validate_rejects_lb_without_nsx`.
- [ ] 22. `test_library_vs_template_fallback`.

## Integration tests (gated)

- [ ] 23. `RUN_LIVE_VSPHERE=1` end-to-end against a homelab vCenter.

## Documentation

- [ ] 24. Author `provisioning/venues/vsphere/README.md` cross-linking the
  resource model, lifecycle, vpn-join, and the vSphere interop client spec.
