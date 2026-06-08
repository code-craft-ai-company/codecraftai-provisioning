# Tasks — Vultr Cloud Provisioner

## Scaffolding

- [x] 1. Create `provisioning/venues/vultr/` tree per `design.md`.
- [ ] 2. Add `codecraftai-interop-vultr` dep (built on (deferred: cross-repo dependency wiring owned by package packaging step)
  `codecraftai-restclient-base`).
  > Deviation: per the M13 directive the venue calls the Vultr v2 REST API
  > directly via `requests` (same pattern as the AWS venue using boto3); no
  > separate interop package.  The REST surface lives in `vultrclient.py`.
- [x] 3. Declare `VultrValidationError`, `VultrConflictError`,
  `ConfirmationRequiredError` in `vultrerrors.py`.

## Resolver and Translator

- [x] 4. Implement `VultrResolver.image_to_os_id(family, version, arch)`
  consulting `GET /os`.
- [x] 5. Implement `VultrResolver.size_to_plan(size_hint, accelerators)`.
- [x] 6. Implement `VultrTagTranslator.to_vultr(neutral_tags)` /
  `from_vultr(strings)` with round-trip identity.

## Validate / Plan / Apply / Destroy / Inventory

- [x] 7. Implement `VultrCloudProvisioner.validate(spec, aspects)` rejecting
  interconnect and shared-FS asks.
- [x] 8. Implement `VultrPlanBuilder.plan(spec, aspects)`.
- [x] 9. Implement `VultrApplyStages.apply_network_and_firewall`.
- [x] 10. Implement `VultrApplyStages.apply_instances_and_blocks` with
  base64 `user_data` rendering.
- [x] 11. Implement `VultrApplyStages.apply_object_storage_and_dns`.
- [x] 12. Implement `VultrDestroyStages.destroy(spec, aspects)` reversing
  apply, calling `IVPNControlPlane.delete_device` after Instance delete.
- [x] 13. Implement `VultrInventory.list_run(spec, aspects)`.
- [x] 14. Persist inventory under
  `.output/provisioning/<runid>/vultr-inventory.json`.

## Property tests (hypothesis)

- [x] 15. `test_apply_idempotent`.
- [x] 16. `test_destroy_is_inverse_of_apply`.
- [x] 17. `test_tag_round_trip_identity`.
- [x] 18. `test_validate_rejects_interconnect_and_shared_fs`.

## Integration tests (gated)

- [ ] 19. `RUN_LIVE_VULTR=1` end-to-end against a sandbox account. (deferred: live-integration end-to-end test gated on real hardware/account)
  > Not implemented: requires a live Vultr sandbox account; out of scope for
  > the offline mock-only test environment.

## Documentation

- [x] 20. Author `provisioning/venues/vultr/README.md` cross-linking the
  resource model, lifecycle, vpn-join, and the Vultr interop client.
