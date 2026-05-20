# Tasks — Proxmox VE Provisioner

## Scaffolding

- [ ] 1. Create `provisioning/venues/proxmox/` tree per `design.md`.
- [ ] 2. Add `automojo-interop-proxmox` dep.
- [ ] 3. Declare `PveValidationError`, `PveConflictError`,
  `ConfirmationRequiredError` in `pveerrors.py`.

## Resolver and Translator

- [ ] 4. Implement `PveResolver.image_to_template_or_url(family, version, arch)`.
- [ ] 5. Implement `PveResolver.size_to_hardware(size_hint)`.
- [ ] 6. Implement `PveResolver.pick_storage(required_gb, node, content_type)`.
- [ ] 7. Implement `PveTagTranslator.to_pve(neutral_tags)` /
  `from_pve(string_list)` with round-trip identity.

## Validate / Plan / Apply / Destroy / Inventory

- [ ] 8. Implement `ProxmoxCloudProvisioner.validate(spec, aspects)` rejecting
  unsupported kinds.
- [ ] 9. Implement `PvePlanBuilder.plan(spec, aspects)`.
- [ ] 10. Implement `PveApplyStages.apply_networking` (SDN VNet or bridge +
  firewall rules).
- [ ] 11. Implement `PveApplyStages.apply_vms` clone-from-template, disk
  attach, `cicustom` upload + reference, tags, power-on.
- [ ] 12. Implement `PveCloudInitRenderer.render_and_upload(snippet, aspects)`
  including SHA256 dedup.
- [ ] 13. Implement `PveDestroyStages.destroy(spec, aspects)` reversing apply,
  calling `IVPNControlPlane.delete_device` after VM delete.
- [ ] 14. Implement `PveInventory.list_run(spec, aspects)` across all cluster
  nodes.
- [ ] 15. Persist inventory under
  `.output/provisioning/<runid>/pve-inventory.json`.

## Property tests (hypothesis)

- [ ] 16. `test_apply_idempotent`.
- [ ] 17. `test_destroy_is_inverse_of_apply`.
- [ ] 18. `test_tag_round_trip_identity`.
- [ ] 19. `test_snippet_upload_dedup`.
- [ ] 20. `test_validate_rejects_unsupported_kinds`.

## Integration tests (gated)

- [ ] 21. `RUN_LIVE_PVE=1` end-to-end against a homelab cluster.

## Documentation

- [ ] 22. Author `provisioning/venues/proxmox/README.md` cross-linking the
  resource model, lifecycle, vpn-join, and the Proxmox interop client.
