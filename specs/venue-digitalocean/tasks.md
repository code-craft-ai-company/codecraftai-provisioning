# Tasks — DigitalOcean Cloud Provisioner

## Scaffolding

- [ ] 1. Create `provisioning/venues/digitalocean/` tree per `design.md`.
- [ ] 2. Add `automojo-interop-digitalocean` + `pydo` deps to `pyproject.toml`.
- [ ] 3. Declare `DoValidationError`, `DoConflictError`,
  `ConfirmationRequiredError` in `doerrors.py`.

## Resolver and Translator

- [ ] 4. Implement `DoResolver.image_to_slug(family, version, arch)`.
- [ ] 5. Implement `DoResolver.size_to_slug(size_hint, accelerators)` covering
  the GPU SKUs (`gpu-h100x1`, `gpu-h100x8`).
- [ ] 6. Implement `DoTagTranslator.to_do(neutral_tags)` encoding `k=v` strings,
  and `from_do(strings)` recovering the neutral form.

## Validate

- [ ] 7. Implement `DigitalOceanCloudProvisioner.validate(spec, aspects)`
  rejecting `CloudSharedFilesystem(LUSTRE/WEKA/VAST/GPFS)` and
  `CloudInterconnect != NONE`.
- [ ] 8. Warn on `CloudLoadBalancer` (v1.5 stub).

## Plan / Apply / Destroy / Inventory

- [ ] 9. Implement `DoPlanBuilder.plan(spec, aspects)`.
- [ ] 10. Implement `DoApplyStages.apply_network_and_firewall`.
- [ ] 11. Implement `DoApplyStages.apply_droplets_and_volumes` with `user_data`
  rendering for `vpn_join`.
- [ ] 12. Implement `DoApplyStages.apply_spaces_and_dns`.
- [ ] 13. Implement `DoDestroyStages.destroy(spec, aspects)` in reverse order,
  calling `IVPNControlPlane.delete_device` after Droplet destroy.
- [ ] 14. Implement `DoInventory.list_run(spec, aspects)`.
- [ ] 15. Persist inventory under
  `.output/provisioning/<runid>/do-inventory.json`.

## Property tests (hypothesis)

- [ ] 16. `test_apply_idempotent`.
- [ ] 17. `test_destroy_is_inverse_of_apply`.
- [ ] 18. `test_tag_round_trip_identity` (with `=` escaping in values).
- [ ] 19. `test_validate_rejects_unsupported_shared_fs_kinds`.
- [ ] 20. `test_validate_rejects_interconnect_requests`.

## Integration tests (gated)

- [ ] 21. `RUN_LIVE_DO=1` end-to-end against a sandbox account.

## Documentation

- [ ] 22. Author `provisioning/venues/digitalocean/README.md` cross-linking the
  resource model, lifecycle, vpn-join, and the DO interop client.
