# Tasks — Nebius Provisioner

## Scaffolding

- [ ] 1. Create `provisioning/venues/nebius/` tree per `design.md`.
- [ ] 2. Add `automojo-interop-nebius` dep.
- [ ] 3. Declare `NebiusValidationError`, `NebiusConflictError`,
  `ConfirmationRequiredError` in `nebiuserrors.py`.

## Resolver and Translator

- [ ] 4. Implement `NebiusResolver.image_to_id(family, version, arch)`.
- [ ] 5. Implement `NebiusResolver.size_to_preset(size_hint, accelerators,
  interconnect)`.
- [ ] 6. Implement `NebiusLabelTranslator.to_nebius(neutral_tags)` /
  `from_nebius(d)` with round-trip identity.

## Validate / Plan / Apply / Destroy / Inventory

- [ ] 7. Implement `NebiusCloudProvisioner.validate(spec, aspects)` rejecting
  LB and shared-FS-provision asks.
- [ ] 8. Validate IB-platform compatibility.
- [ ] 9. Implement `NebiusPlanBuilder.plan(spec, aspects)`.
- [ ] 10. Implement `NebiusApplyStages.apply_network_and_security`.
- [ ] 11. Implement `NebiusGpuCluster.ensure_and_attach(spec, aspects)`.
- [ ] 12. Implement `NebiusApplyStages.apply_instances_and_disks` with
  `metadata.user-data` rendering.
- [ ] 13. Implement `NebiusApplyStages.apply_storage_and_dns`.
- [ ] 14. Implement `NebiusDestroyStages.destroy(spec, aspects)` reversing
  apply, calling `IVPNControlPlane.delete_device` after Instance terminate.
- [ ] 15. Implement `NebiusInventory.list_run(spec, aspects)`.
- [ ] 16. Persist inventory under
  `.output/provisioning/<runid>/nebius-inventory.json`.

## Property tests (hypothesis)

- [ ] 17. `test_apply_idempotent`.
- [ ] 18. `test_destroy_is_inverse_of_apply`.
- [ ] 19. `test_label_round_trip_identity_for_conformant_inputs`.
- [ ] 20. `test_gpu_cluster_grouping`.
- [ ] 21. `test_validate_rejects_lb_and_fs_provision`.

## Integration tests (gated)

- [ ] 22. `RUN_LIVE_NEBIUS=1` end-to-end against a sandbox project.

## Documentation

- [ ] 23. Author `provisioning/venues/nebius/README.md` cross-linking the
  resource model, lifecycle, vpn-join, and the Nebius interop client.
