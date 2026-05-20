# Tasks — Hyper-V Provisioner

## Scaffolding

- [x] 1. Create `provisioning/venues/hyperv/` tree per `design.md`.
- [ ] 2. Add `automojo-interop-hyperv` dep. (deferred: cross-repo dependency wiring owned by package packaging step)
- [x] 3. Declare `HvValidationError`, `HvConflictError`,
  `ConfirmationRequiredError` in `hverrors.py`.

## Resolver and Translator

- [x] 4. Implement `HvResolver.image_to_parent_vhd(family, version, arch)`.
- [x] 5. Implement `HvResolver.size_to_hardware(size_hint)`.
- [x] 6. Implement `HvNotesTranslator.encode(neutral_tags, run_id)` /
  `decode(notes_str)` with round-trip identity.

## Validate / Plan / Apply / Destroy / Inventory

- [x] 7. Implement `HypervCloudProvisioner.validate(spec, aspects)` rejecting
  unsupported kinds.
- [x] 8. Implement `HvPlanBuilder.plan(spec, aspects)`.
- [x] 9. Implement `HvApplyStages.apply_switches`.
- [x] 10. Implement `HvApplyStages.apply_vms` (differencing VHDX, `New-VM`,
  `Set-VMProcessor`/`Set-VMMemory`, `Add-VMHardDiskDrive`, network adapter,
  `Set-VM -Notes`, ISO mount, `Start-VM`).
- [x] 11. Implement `HvCloudInitRenderer.build_iso(user_data, network_config,
  vpn_join)` and `HvCloudInitRenderer.build_setupcomplete(vpn_join)` for
  Windows.
- [x] 12. Implement `HvDestroyStages.destroy(spec, aspects)` reversing apply,
  calling `IVPNControlPlane.delete_device` after VM removal.
- [x] 13. Implement `HvInventory.list_run(spec, aspects)` using KVP-reported
  IPs.
- [x] 14. Persist inventory under
  `.output/provisioning/<runid>/hyperv-inventory.json`.

## Property tests (hypothesis)

- [x] 15. `test_apply_idempotent`.
- [x] 16. `test_destroy_is_inverse_of_apply`.
- [x] 17. `test_notes_json_tag_round_trip_identity`.
- [x] 18. `test_validate_rejects_unsupported_kinds`.

## Integration tests (gated)

- [ ] 19. `RUN_LIVE_HYPERV=1` end-to-end against a homelab host. (deferred: live-integration end-to-end test gated on real hardware/account)

## Documentation

- [x] 20. Author `provisioning/venues/hyperv/README.md` cross-linking the
  resource model, lifecycle, vpn-join, and the Hyper-V interop client.
