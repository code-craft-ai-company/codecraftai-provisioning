# Tasks — Hyper-V Provisioner

## Scaffolding

- [ ] 1. Create `provisioning/venues/hyperv/` tree per `design.md`.
- [ ] 2. Add `automojo-interop-hyperv` dep.
- [ ] 3. Declare `HvValidationError`, `HvConflictError`,
  `ConfirmationRequiredError` in `hverrors.py`.

## Resolver and Translator

- [ ] 4. Implement `HvResolver.image_to_parent_vhd(family, version, arch)`.
- [ ] 5. Implement `HvResolver.size_to_hardware(size_hint)`.
- [ ] 6. Implement `HvNotesTranslator.encode(neutral_tags, run_id)` /
  `decode(notes_str)` with round-trip identity.

## Validate / Plan / Apply / Destroy / Inventory

- [ ] 7. Implement `HypervCloudProvisioner.validate(spec, aspects)` rejecting
  unsupported kinds.
- [ ] 8. Implement `HvPlanBuilder.plan(spec, aspects)`.
- [ ] 9. Implement `HvApplyStages.apply_switches`.
- [ ] 10. Implement `HvApplyStages.apply_vms` (differencing VHDX, `New-VM`,
  `Set-VMProcessor`/`Set-VMMemory`, `Add-VMHardDiskDrive`, network adapter,
  `Set-VM -Notes`, ISO mount, `Start-VM`).
- [ ] 11. Implement `HvCloudInitRenderer.build_iso(user_data, network_config,
  vpn_join)` and `HvCloudInitRenderer.build_setupcomplete(vpn_join)` for
  Windows.
- [ ] 12. Implement `HvDestroyStages.destroy(spec, aspects)` reversing apply,
  calling `IVPNControlPlane.delete_device` after VM removal.
- [ ] 13. Implement `HvInventory.list_run(spec, aspects)` using KVP-reported
  IPs.
- [ ] 14. Persist inventory under
  `.output/provisioning/<runid>/hyperv-inventory.json`.

## Property tests (hypothesis)

- [ ] 15. `test_apply_idempotent`.
- [ ] 16. `test_destroy_is_inverse_of_apply`.
- [ ] 17. `test_notes_json_tag_round_trip_identity`.
- [ ] 18. `test_validate_rejects_unsupported_kinds`.

## Integration tests (gated)

- [ ] 19. `RUN_LIVE_HYPERV=1` end-to-end against a homelab host.

## Documentation

- [ ] 20. Author `provisioning/venues/hyperv/README.md` cross-linking the
  resource model, lifecycle, vpn-join, and the Hyper-V interop client.
