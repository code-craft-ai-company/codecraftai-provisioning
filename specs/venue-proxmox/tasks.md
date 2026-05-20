# Tasks — Proxmox VE Provisioner

## Scaffolding

- [x] 1. Create `provisioning/venues/proxmox/` tree per `design.md`.
- [x] 2. Add `automojo-interop-proxmox` dep.
- [x] 3. Declare `PveValidationError`, `PveConflictError`,
  `ConfirmationRequiredError` in `pveerrors.py`.

## Resolver and Translator

- [x] 4. Implement `PveResolver.image_to_template_or_url(family, version, arch)`.
- [x] 5. Implement `PveResolver.size_to_hardware(size_hint)`.
- [x] 6. Implement `PveResolver.pick_storage(required_gb, node, content_type)`.
- [x] 7. Implement `PveTagTranslator.to_pve(neutral_tags)` /
  `from_pve(string_list)` with round-trip identity.

## Validate / Plan / Apply / Destroy / Inventory

- [x] 8. Implement `ProxmoxCloudProvisioner.validate(spec, aspects)` rejecting
  unsupported kinds.
- [x] 9. Implement `PvePlanBuilder.plan(spec, aspects)`.
- [x] 10. Implement `PveApplyStages.apply_networking` (SDN VNet or bridge +
  firewall rules).
- [x] 11. Implement `PveApplyStages.apply_vms` clone-from-template, disk
  attach, `cicustom` upload + reference, tags, power-on.
- [x] 12. Implement `PveCloudInitRenderer.render_and_upload(snippet, aspects)`
  including SHA256 dedup.
- [x] 13. Implement `PveDestroyStages.destroy(spec, aspects)` reversing apply,
  calling `IVPNControlPlane.delete_device` after VM delete.
- [x] 14. Implement `PveInventory.list_run(spec, aspects)` across all cluster
  nodes.
- [x] 15. Persist inventory under
  `.output/provisioning/<runid>/pve-inventory.json`.

## Property tests (hypothesis)

- [x] 16. `test_apply_idempotent`.
- [x] 17. `test_destroy_is_inverse_of_apply`.
- [x] 18. `test_tag_round_trip_identity`.
- [x] 19. `test_snippet_upload_dedup`.
- [x] 20. `test_validate_rejects_unsupported_kinds`.

## Integration tests (gated)

- [ ] 21. `RUN_LIVE_PVE=1` end-to-end against a homelab cluster. (deferred: live-integration end-to-end test gated on real hardware/account)

## Documentation

- [ ] 22. Author `provisioning/venues/proxmox/README.md` cross-linking the (deferred: README.md not yet authored)
  resource model, lifecycle, vpn-join, and the Proxmox interop client.
