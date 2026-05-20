# Tasks — libvirt / KVM Provisioner

## Scaffolding

- [ ] 1. Create `provisioning/venues/libvirt/` tree per `design.md`.
- [ ] 2. Add `automojo-interop-libvirt` + `libvirt-python` deps.
- [ ] 3. Declare `LvValidationError`, `LvConflictError`,
  `ConfirmationRequiredError` in `lverrors.py`.

## Builders and Translators

- [ ] 4. Implement `LvDomainXmlBuilder.build(spec_vm, network, volume,
  seed_iso)` producing a deterministic Domain XML string.
- [ ] 5. Implement `LvMetadataTranslator.embed(neutral_tags, run_id)` and
  `extract(domain_xml)` with round-trip identity.
- [ ] 6. Implement `LvSeedIsoBuilder.build(user_data, meta_data, network_config)`
  using `genisoimage`/`xorriso` via `ICommandRunner`.

## Validate / Plan / Apply / Destroy / Inventory

- [ ] 7. Implement `LibvirtCloudProvisioner.validate(spec, aspects)` rejecting
  unsupported kinds.
- [ ] 8. Implement `LvPlanBuilder.plan(spec, aspects)`.
- [ ] 9. Implement `LvApplyStages.apply_networks_and_pools`.
- [ ] 10. Implement `LvApplyStages.apply_volumes` including base-image
  backing-chain clones.
- [ ] 11. Implement `LvApplyStages.apply_domains` including seed-ISO upload
  + Domain define+start.
- [ ] 12. Implement `LvDestroyStages.destroy(spec, aspects)` reversing apply,
  calling `IVPNControlPlane.delete_device` after Domain undefine.
- [ ] 13. Implement `LvInventory.list_run(spec, aspects)` using QEMU guest
  agent for IP discovery when available.
- [ ] 14. Persist inventory under
  `.output/provisioning/<runid>/libvirt-inventory.json`.

## Property tests (hypothesis)

- [ ] 15. `test_apply_idempotent`.
- [ ] 16. `test_destroy_is_inverse_of_apply`.
- [ ] 17. `test_metadata_tag_round_trip_identity` covering namespaces, colons,
  and whitespace.
- [ ] 18. `test_seed_iso_content_hash_deterministic`.
- [ ] 19. `test_validate_rejects_unsupported_kinds`.

## Integration tests (gated)

- [ ] 20. `RUN_LIVE_LIBVIRT=1` end-to-end against a local libvirt daemon.

## Documentation

- [ ] 21. Author `provisioning/venues/libvirt/README.md` cross-linking the
  resource model, lifecycle, vpn-join, and the libvirt interop client.
