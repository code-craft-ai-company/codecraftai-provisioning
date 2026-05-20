# Tasks — libvirt / KVM Provisioner

## Scaffolding

- [x] 1. Create `provisioning/venues/libvirt/` tree per `design.md`.
- [ ] 2. Add `automojo-interop-libvirt` + `libvirt-python` deps.
- [x] 3. Declare `LvValidationError`, `LvConflictError`,
  `ConfirmationRequiredError` in `lverrors.py`.

## Builders and Translators

- [x] 4. Implement `LvDomainXmlBuilder.build(spec_vm, network, volume,
  seed_iso)` producing a deterministic Domain XML string.
- [x] 5. Implement `LvMetadataTranslator.embed(neutral_tags, run_id)` and
  `extract(domain_xml)` with round-trip identity.
- [x] 6. Implement `LvSeedIsoBuilder.build(user_data, meta_data, network_config)`
  using `genisoimage`/`xorriso` via `ICommandRunner`.

## Validate / Plan / Apply / Destroy / Inventory

- [x] 7. Implement `LibvirtCloudProvisioner.validate(spec, aspects)` rejecting
  unsupported kinds.
- [x] 8. Implement `LvPlanBuilder.plan(spec, aspects)`.
- [x] 9. Implement `LvApplyStages.apply_networks_and_pools`.
- [x] 10. Implement `LvApplyStages.apply_volumes` including base-image
  backing-chain clones.
- [x] 11. Implement `LvApplyStages.apply_domains` including seed-ISO upload
  + Domain define+start.
- [x] 12. Implement `LvDestroyStages.destroy(spec, aspects)` reversing apply,
  calling `IVPNControlPlane.delete_device` after Domain undefine.
- [x] 13. Implement `LvInventory.list_run(spec, aspects)` using QEMU guest
  agent for IP discovery when available.
- [x] 14. Persist inventory under
  `.output/provisioning/<runid>/libvirt-inventory.json`.

## Property tests (hypothesis)

- [x] 15. `test_apply_idempotent`.
- [x] 16. `test_destroy_is_inverse_of_apply`.
- [x] 17. `test_metadata_tag_round_trip_identity` covering namespaces, colons,
  and whitespace.
- [x] 18. `test_seed_iso_content_hash_deterministic`.
- [x] 19. `test_validate_rejects_unsupported_kinds`.

## Integration tests (gated)

- [ ] 20. `RUN_LIVE_LIBVIRT=1` end-to-end against a local libvirt daemon.

## Documentation

- [x] 21. Author `provisioning/venues/libvirt/README.md` cross-linking the
  resource model, lifecycle, vpn-join, and the libvirt interop client.
