# Tasks — RunPod Workload Provisioner

## Scaffolding

- [ ] 1. Create `provisioning/venues/runpod/` tree per `design.md`.
- [ ] 2. Add `automojo-interop-runpod` dep.
- [ ] 3. Declare `RpValidationError`, `RpCapacityError`,
  `ConfirmationRequiredError` in `rperrors.py`.

## Resolver and Translator

- [ ] 4. Implement `RpResolver.accelerator_to_gpu_type(accel_spec)` and
  `RpResolver.image_to_template_or_url(family, version, arch)`.
- [ ] 5. Implement `RpSidecarTag.write(neutral_tags, pod_id)` and
  `read(pod_id)` with round-trip identity.
- [ ] 6. Implement `RpContainerStartRenderer.render(spec_pod, vpn_join)`
  producing a deterministic `containerStartScript` that installs and starts
  `tailscale` in userspace mode when `vpn_join` is set.

## Validate / Plan / Apply / Destroy / Inventory

- [ ] 7. Implement `RunpodWorkloadProvisioner.validate(spec, aspects)`
  rejecting bucket/LB/DNS/interconnect and warning on unrealised network
  resources.
- [ ] 8. Validate tier capacity for the requested gpuType + region.
- [ ] 9. Implement `RpPlanBuilder.plan(spec, aspects)`.
- [ ] 10. Implement `RpApplyStages.ensure_network_volumes`.
- [ ] 11. Implement `RpApplyStages.apply_pods` honouring Secure vs Community
  tier and rendering the container start script.
- [ ] 12. Implement `RpDestroyStages.destroy(spec, aspects)` reversing
  apply, calling `IVPNControlPlane.delete_device` after Pod terminate.
- [ ] 13. Implement `RpInventory.list_run(spec, aspects)`.
- [ ] 14. Persist sidecar tags under
  `.output/provisioning/<runid>/runpod-tags.json` and inventory under
  `.output/provisioning/<runid>/runpod-inventory.json`.

## Property tests (hypothesis)

- [ ] 15. `test_apply_idempotent`.
- [ ] 16. `test_destroy_is_inverse_of_apply`.
- [ ] 17. `test_sidecar_tag_round_trip_identity`.
- [ ] 18. `test_userspace_tailscale_start_script_hash_deterministic`.
- [ ] 19. `test_secure_vs_community_branch`.
- [ ] 20. `test_validate_rejects_bucket_lb_dns_interconnect`.

## Integration tests (gated)

- [ ] 21. `RUN_LIVE_RUNPOD=1` end-to-end against a sandbox account.

## Documentation

- [ ] 22. Author `provisioning/venues/runpod/README.md` cross-linking the
  resource model, lifecycle, workload-venue model, vpn-join, and the
  RunPod interop client.
