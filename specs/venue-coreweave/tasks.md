# Tasks — CoreWeave Workload Provisioner

## Scaffolding

- [ ] 1. Create `provisioning/venues/coreweave/` tree per `design.md`.
- [ ] 2. Add `automojo-interop-coreweave` + `automojo-interop-kubernetes`
  deps.
- [ ] 3. Declare `CwValidationError`, `CwKubeconfigError`,
  `ConfirmationRequiredError` in `cwerrors.py`.

## Selectors and Renderers

- [ ] 4. Implement `CwNodePoolSelector.match(accel_spec, interconnect)`
  consulting CoreWeave node-pool metadata.
- [ ] 5. Implement `CwLabelTranslator.to_k8s(neutral_tags)` /
  `from_k8s(d)` with round-trip identity for conformant inputs.
- [ ] 6. Implement `CwManifestRenderer.render(workload_spec, run_id)` for
  Deployments, StatefulSets, Jobs, Services, Ingresses, Secrets, PVCs.
- [ ] 7. Implement `CwSunkRenderer.render(workload_spec, run_id)` for the
  Sunk Slurm-on-K8s manifest bundle.
- [ ] 8. Implement `CwVpnSidecar.render(vpn_join, pod_template)` and the
  alternative `render_subnet_router_daemonset(vpn_join)`.

## Validate / Plan / Apply / Destroy / Inventory

- [ ] 9. Implement `CoreweaveWorkloadProvisioner.validate(spec, aspects)`
  including credential presence check, node-pool resolution, Sunk-mode
  gating, and SLURM/RAY/NOMAD enumerant rejection.
- [ ] 10. Implement `CwPlanBuilder.plan(spec, aspects)` mintng kubeconfig
  via `aspects.kubeconfig_ttl`.
- [ ] 11. Implement `CwApplyStages.apply_namespace_and_rbac`.
- [ ] 12. Implement `CwApplyStages.apply_storage_pvcs` for shared-FS CSI
  bindings.
- [ ] 13. Implement `CwApplyStages.apply_workloads` rendering manifests and
  delegating to the K8s interop's `apply_manifest`.
- [ ] 14. Inject VPN sidecar / subnet-router DaemonSet when `vpn_join` set.
- [ ] 15. Implement `CwDestroyStages.destroy(spec, aspects)` in reverse
  dependency order, calling `IVPNControlPlane.delete_device` for every
  registered VPN device.
- [ ] 16. Implement `CwInventory.list_run(spec, aspects)` enumerating
  run-id-labelled K8s resources.
- [ ] 17. Persist inventory under
  `.output/provisioning/<runid>/coreweave-inventory.json`.

## Property tests (hypothesis)

- [ ] 18. `test_apply_idempotent`.
- [ ] 19. `test_destroy_is_inverse_of_apply`.
- [ ] 20. `test_label_round_trip_identity_for_conformant_inputs`.
- [ ] 21. `test_sunk_manifest_bundle_content_hash_deterministic`.
- [ ] 22. `test_vpn_sidecar_vs_subnet_router_branch`.
- [ ] 23. `test_validate_rejects_slurm_ray_nomad_without_sunk`.

## Integration tests (gated)

- [ ] 24. `RUN_LIVE_COREWEAVE=1` end-to-end against a sandbox project.

## Documentation

- [ ] 25. Author `provisioning/venues/coreweave/README.md` cross-linking
  the resource model, lifecycle, workload-venue model, vpn-join, and the
  CoreWeave + Kubernetes interop specs.
