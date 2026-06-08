# Tasks — Oracle Cloud Infrastructure Provisioner

## Scaffolding

- [x] 1. Create `provisioning/venues/oracle/` tree per `design.md`.
- [x] 2. Add `codecraftai-interop-oracle` + `oci` SDK deps.
- [x] 3. Declare `OciValidationError`, `OciConflictError`,
  `ConfirmationRequiredError` in `ocierrors.py`.

## Resolver and Translator

- [x] 4. Implement `OciResolver.image_to_ocid(family, version, arch, region)`.
- [x] 5. Implement `OciResolver.size_to_shape(size_hint, accelerators)`.
- [x] 6. Implement `OciTagTranslator.to_freeform(neutral_tags)` /
  `from_freeform(d)` with round-trip identity.

## Validate / Plan / Apply / Destroy / Inventory

- [x] 7. Implement `OracleCloudProvisioner.validate(spec, aspects)` rejecting
  `CloudInterconnect(kind=EFA|INFINIBAND_*)` and `CloudSharedFilesystem(WEKA)`.
- [x] 8. Validate that RDMA shapes are BM.GPU.
- [x] 9. Implement `OciPlanBuilder.plan(spec, aspects)`.
- [x] 10. Implement `OciApplyStages.apply_vcn_and_security`.
- [x] 11. Implement `OciClusterNetwork.ensure_and_attach(spec, aspects)` for
  RDMA-grouped instances.
- [x] 12. Implement `OciApplyStages.apply_compute_and_volumes` with `user_data`
  rendering.
- [x] 13. Implement `OciApplyStages.apply_storage_and_dns` (File Storage,
  Object Storage, DNS).
- [x] 14. Implement `OciDestroyStages.destroy(spec, aspects)` reversing apply,
  calling `IVPNControlPlane.delete_device` after Instance terminate.
- [x] 15. Implement `OciInventory.list_run(spec, aspects)`.
- [ ] 16. Persist inventory under (deferred: run-inventory file persistence owned by the provisioning engine/state layer; venue exposes inventory())
  `.output/provisioning/<runid>/oci-inventory.json`.

## Property tests (hypothesis)

- [x] 17. `test_apply_idempotent`.
- [x] 18. `test_destroy_is_inverse_of_apply`.
- [x] 19. `test_freeform_tag_round_trip_identity`.
- [x] 20. `test_cluster_network_grouping`.
- [x] 21. `test_validate_rejects_non_oci_interconnect_kinds`.

## Integration tests (gated)

- [ ] 22. `RUN_LIVE_OCI=1` end-to-end against a sandbox tenancy. (deferred: live-integration end-to-end test gated on real hardware/account)

## Documentation

- [ ] 23. Author `provisioning/venues/oracle/README.md` cross-linking the (deferred: README.md not yet authored)
  resource model, lifecycle, vpn-join, and `codecraftai-interop-oracle`.
