# Tasks — Hetzner Cloud Provisioner

## Scaffolding

- [ ] 1. Create `provisioning/venues/hetzner/` tree per `design.md`.
- [ ] 2. Add `automojo-interop-hetzner` + `hcloud` deps.
- [ ] 3. Declare `HetznerValidationError`, `HetznerConflictError`,
  `ConfirmationRequiredError` in `hetznererrors.py`.

## Resolver and Translator

- [ ] 4. Implement `HetznerResolver.image_to_name(family, version, arch)`.
- [ ] 5. Implement `HetznerResolver.size_to_type(size_hint, accelerators)`.
- [ ] 6. Implement `HetznerLabelTranslator.to_hetzner(neutral_tags)` with
  validation against Hetzner label rules, and `from_hetzner(d)`.

## Validate / Plan / Apply / Destroy / Inventory

- [ ] 7. Implement `HetznerCloudProvisioner.validate(spec, aspects)` rejecting
  `CloudObjectBucket`, `CloudInterconnect != NONE`, and shared-FS asks.
- [ ] 8. Implement `HetznerPlanBuilder.plan(spec, aspects)`.
- [ ] 9. Implement `HetznerApplyStages.apply_network_and_firewall`.
- [ ] 10. Implement `HetznerApplyStages.apply_servers_and_volumes` with
  `user_data` for `vpn_join`.
- [ ] 11. Implement `HetznerApplyStages.apply_dns`.
- [ ] 12. Implement `HetznerDestroyStages.destroy(spec, aspects)` reversing
  apply, calling `IVPNControlPlane.delete_device` after Server delete.
- [ ] 13. Implement `HetznerInventory.list_run(spec, aspects)`.
- [ ] 14. Persist inventory under
  `.output/provisioning/<runid>/hetzner-inventory.json`.

## Property tests (hypothesis)

- [ ] 15. `test_apply_idempotent`.
- [ ] 16. `test_destroy_is_inverse_of_apply`.
- [ ] 17. `test_label_round_trip_identity_for_conformant_inputs`.
- [ ] 18. `test_validate_rejects_object_bucket_and_interconnect`.

## Integration tests (gated)

- [ ] 19. `RUN_LIVE_HETZNER=1` end-to-end against a sandbox project.

## Documentation

- [ ] 20. Author `provisioning/venues/hetzner/README.md` cross-linking the
  resource model, lifecycle, vpn-join, and the Hetzner interop client.
