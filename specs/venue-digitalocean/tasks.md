# Tasks — DigitalOcean Cloud Provisioner

## Scaffolding

- [x] 1. Create `provisioning/venues/digitalocean/` tree per `design.md`.
- [ ] 2. Add `automojo-interop-digitalocean` + `pydo` deps to `pyproject.toml`. (deferred: cross-repo dependency wiring owned by package packaging step)
- [x] 3. Declare `DoValidationError`, `DoConflictError`,
  `ConfirmationRequiredError` in `doerrors.py`.

## Resolver and Translator

- [x] 4. Implement `DoResolver.image_to_slug(family, version, arch)`.
- [x] 5. Implement `DoResolver.size_to_slug(size_hint, accelerators)` covering
  the GPU SKUs (`gpu-h100x1`, `gpu-h100x8`).
- [x] 6. Implement `DoTagTranslator.to_do(neutral_tags)` encoding `k=v` strings,
  and `from_do(strings)` recovering the neutral form.

## Validate

- [x] 7. Implement `DigitalOceanCloudProvisioner.validate(spec, aspects)`
  rejecting `CloudSharedFilesystem(LUSTRE/WEKA/VAST/GPFS)` and
  `CloudInterconnect != NONE`.
- [x] 8. Warn on `CloudLoadBalancer` (v1.5 stub).

## Plan / Apply / Destroy / Inventory

- [x] 9. Implement `DoPlanBuilder.plan(spec, aspects)`.
- [x] 10. Implement `DoApplyStages.apply_network_and_firewall`.
- [x] 11. Implement `DoApplyStages.apply_droplets_and_volumes` with `user_data`
  rendering for `vpn_join`.
- [x] 12. Implement `DoApplyStages.apply_spaces_and_dns`.
- [x] 13. Implement `DoDestroyStages.destroy(spec, aspects)` in reverse order,
  calling `IVPNControlPlane.delete_device` after Droplet destroy.
- [x] 14. Implement `DoInventory.list_run(spec, aspects)`.
- [x] 15. Persist inventory under
  `.output/provisioning/<runid>/do-inventory.json`.

## Property tests (hypothesis)

- [x] 16. `test_apply_idempotent`.
- [x] 17. `test_destroy_is_inverse_of_apply`.
- [x] 18. `test_tag_round_trip_identity` (with `=` escaping in values).
- [x] 19. `test_validate_rejects_unsupported_shared_fs_kinds`.
- [x] 20. `test_validate_rejects_interconnect_requests`.

## Integration tests (gated)

- [ ] 21. `RUN_LIVE_DO=1` end-to-end against a sandbox account. (deferred: live-integration end-to-end test gated on real hardware/account)

## Documentation

- [x] 22. Author `provisioning/venues/digitalocean/README.md` cross-linking the
  resource model, lifecycle, vpn-join, and the DO interop client.
