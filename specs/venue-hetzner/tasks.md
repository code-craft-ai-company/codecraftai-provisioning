# Tasks — Hetzner Cloud Provisioner

## Scaffolding

- [x] 1. Create `provisioning/venues/hetzner/` tree per `design.md`.
- [ ] 2. Add `automojo-interop-hetzner` + `hcloud` deps.
- [x] 3. Declare `HetznerValidationError`, `HetznerConflictError`,
  `ConfirmationRequiredError` in `hetznererrors.py`.

## Resolver and Translator

- [x] 4. Implement `HetznerResolver.image_to_name(family, version, arch)`.
- [x] 5. Implement `HetznerResolver.size_to_type(size_hint, accelerators)`.
- [x] 6. Implement `HetznerLabelTranslator.to_hetzner(neutral_tags)` with
  validation against Hetzner label rules, and `from_hetzner(d)`.

## Validate / Plan / Apply / Destroy / Inventory

- [x] 7. Implement `HetznerCloudProvisioner.validate(spec, aspects)` rejecting
  `CloudObjectBucket`, `CloudInterconnect != NONE`, and shared-FS asks.
- [x] 8. Implement `HetznerPlanBuilder.plan(spec, aspects)`.
- [x] 9. Implement `HetznerApplyStages.apply_network_and_firewall`.
- [x] 10. Implement `HetznerApplyStages.apply_servers_and_volumes` with
  `user_data` for `vpn_join`.
- [x] 11. Implement `HetznerApplyStages.apply_dns`.
- [x] 12. Implement `HetznerDestroyStages.destroy(spec, aspects)` reversing
  apply, calling `IVPNControlPlane.delete_device` after Server delete.
- [x] 13. Implement `HetznerInventory.list_run(spec, aspects)`.
- [x] 14. Persist inventory under
  `.output/provisioning/<runid>/hetzner-inventory.json`.

## Property tests (hypothesis)

- [x] 15. `test_apply_idempotent`.
- [x] 16. `test_destroy_is_inverse_of_apply`.
- [x] 17. `test_label_round_trip_identity_for_conformant_inputs`.
- [x] 18. `test_validate_rejects_object_bucket_and_interconnect`.

## Integration tests (gated)

- [ ] 19. `RUN_LIVE_HETZNER=1` end-to-end against a sandbox project.

## Documentation

- [x] 20. Author `provisioning/venues/hetzner/README.md` cross-linking the
  resource model, lifecycle, vpn-join, and the Hetzner interop client.
