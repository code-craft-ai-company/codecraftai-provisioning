# Tasks — GCP Cloud Provisioner

## Scaffolding

- [x] 1. Create `provisioning/venues/google/` tree per `design.md`.
- [x] 2. Add `codecraftai-interop-gcp` + `google-cloud-compute`,
  `google-cloud-tpu`, `google-cloud-storage`, `google-cloud-dns`,
  `google-cloud-filestore`, `google-cloud-parallelstore` deps.
- [x] 3. Declare `GcpValidationError`, `GcpConflictError`,
  `ConfirmationRequiredError` in `gcperrors.py`.

## Resolver and Translator

- [x] 4. Implement `GcpResolver.image_to_uri(family, version, arch)`.
- [x] 5. Implement `GcpResolver.size_to_machine_type(size_hint)`.
- [x] 6. Implement `GcpResolver.accelerator_to_family(accel_spec)` returning
  `(machine_type, guest_accelerator_type)` for GPUs and routing TPUs to the TPU
  branch.
- [x] 7. Implement `GcpLabelTranslator.to_labels(neutral_tags)` with sanitisation
  + warning emission, and `from_labels(d)` returning the neutral form.

## Validate

- [x] 8. Implement `GcpCloudProvisioner.validate(spec, aspects)` rejecting EFA,
  INFINIBAND_*, and WEKA asks with substitution suggestions.
- [x] 9. Validate TPU specs: require `model`, reject `subnet` if the TPU API
  refuses VPC attachment for the model.
- [x] 10. Validate compact-placement support per (zone, family).

## Plan

- [x] 11. Implement `GcpPlanBuilder.plan(spec, aspects)` with per-service `get`
  probes.
- [x] 12. Branch TPU resources to `GcpTpuBranch.plan`.

## Apply

- [x] 13. Implement `GcpApplyStages.apply_network_and_firewall`.
- [x] 14. Implement `GcpApplyStages.apply_compute` including ResourcePolicy
  (compact placement) attachment.
- [x] 15. Implement `GcpTpuBranch.apply` using
  `tpu_v2.NodeServiceClient.create_node`.
- [x] 16. Implement `GcpApplyStages.apply_storage_and_dns`.
- [x] 17. Wire `GcpUserDataRenderer` for `vpn_join` →
  `metadata.items["user-data"]`.
- [x] 18. Persist inventory under
  `.output/provisioning/<runid>/gcp-inventory.json`.

## Destroy

- [x] 19. Implement `GcpDestroyStages.destroy(spec, aspects)`.
- [x] 20. Implement `GcpTpuBranch.destroy`.
- [x] 21. Call `IVPNControlPlane.delete_device` for VPN-joined instances.

## Inventory

- [x] 22. Implement `GcpInventory.list_run(spec, aspects)`.

## Property tests (hypothesis)

- [x] 23. `test_apply_idempotent`.
- [x] 24. `test_destroy_is_inverse_of_apply`.
- [x] 25. `test_label_round_trip_identity_for_conformant_inputs`.
- [x] 26. `test_compact_placement_grouping`.
- [x] 27. `test_tpu_branch_isolation` — TPU spec produces zero Compute Engine
  calls, GPU spec produces zero TPU API calls.

## Integration tests (gated)

- [ ] 28. `RUN_LIVE_GCP=1` end-to-end against a sandbox project. (deferred: live-integration end-to-end test gated on real hardware/account)

## Documentation

- [ ] 29. Author `provisioning/venues/google/README.md` cross-linking the (deferred: README.md not yet authored)
  resource model, lifecycle, vpn-join, and `codecraftai-interop-gcp`.
