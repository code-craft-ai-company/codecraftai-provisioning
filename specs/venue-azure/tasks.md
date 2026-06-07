# Tasks — Azure Cloud Provisioner

## Scaffolding

- [x] 1. Create `provisioning/venues/azure/` tree per `design.md`.
- [ ] 2. Add `codecraftai-interop-azure` + `azure-identity` + `azure-mgmt-*` deps to (deferred: cross-repo dependency wiring owned by package packaging step)
  `pyproject.toml`.
- [x] 3. Declare `AzureValidationError`, `AzureConflictError`,
  `ConfirmationRequiredError` in `azureerrors.py`.

## Resolver and Translator

- [x] 4. Implement `AzureResolver.image_to_urn(family, version, arch)` returning
  Azure Marketplace URNs for Ubuntu, Debian, RHEL, Windows Server.
- [x] 5. Implement `AzureResolver.size_to_vm_size(size_hint)`.
- [x] 6. Implement `AzureResolver.accelerator_to_sku(accel_spec, interconnect)`
  driving NDv5 / NCv4 selection.
- [x] 7. Implement `AzureTagTranslator.to_azure(neutral_tags)` with collision
  detection, and `from_azure(d)` returning the neutral form.

## Validate

- [x] 8. Implement `AzureCloudProvisioner.validate(spec, aspects)` walking every
  resource and rejecting Azure-incompatible asks (EFA, OCI_RDMA, WEKA).
- [x] 9. Verify every resource carries a resolvable ResourceGroup reference.
- [x] 10. Auto-create a `<apod>-ppg` Proximity Placement Group entry in the plan
  when any IB-requesting VM lacks a `placement_group`.

## Plan

- [x] 11. Implement `AzurePlanBuilder.plan(spec, aspects)` issuing `.get(...)`
  calls per resource and emitting `PlanAction`s.
- [x] 12. Detect drift on NSG rules, VM size, disk type, and tags.
- [x] 13. Treat VM SKU changes across family as `UPDATE-by-recreate`.

## Apply

- [x] 14. Implement `AzureApplyStages.apply_resource_group_and_network`.
- [x] 15. Implement `AzureApplyStages.apply_compute` including PPG attachment
  for IB SKUs.
- [x] 16. Implement `AzureApplyStages.apply_storage_and_dns`.
- [x] 17. Wire `AzureCustomDataRenderer` so `vpn_join` is base64 `custom_data`
  for Linux VMs and a Custom Script Extension for Windows VMs.
- [ ] 18. Persist run inventory under (deferred: run-inventory file persistence owned by the provisioning engine/state layer; venue exposes inventory())
  `.output/provisioning/<runid>/azure-inventory.json`.
- [x] 19. Refuse DELETE actions unless `aspects.confirm`.

## Destroy

- [x] 20. Implement `AzureDestroyStages.destroy(spec, aspects)` reversing apply
  order, only removing the ResourceGroup when empty and owned by the run-id.
- [x] 21. Call `IVPNControlPlane.delete_device` for each VPN-joined VM after
  termination.

## Inventory

- [x] 22. Implement `AzureInventory.list_run(spec, aspects)`.

## Property tests (hypothesis)

- [x] 23. `test_apply_idempotent` — re-apply produces zero mutating calls.
- [x] 24. `test_destroy_is_inverse_of_apply` — empty ResourceGroup state.
- [x] 25. `test_tag_round_trip_identity` — collision-free tag sets round-trip as
  identity.
- [x] 26. `test_ndv5_ppg_grouping` — VMs sharing `interconnect_group` land in the
  same PPG.

## Integration tests (gated)

- [ ] 27. `RUN_LIVE_AZURE=1` end-to-end against a sandbox subscription. (deferred: live-integration end-to-end test gated on real hardware/account)

## Documentation

- [ ] 28. Author `provisioning/venues/azure/README.md` cross-linking the resource (deferred: README.md not yet authored)
  model, lifecycle, vpn-join, and `codecraftai-interop-azure`.
