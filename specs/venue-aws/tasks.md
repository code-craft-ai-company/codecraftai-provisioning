# Tasks — AWS Cloud Provisioner

## Scaffolding

- [x] 1. Create `provisioning/venues/aws/` module tree with the file layout from
  `design.md`.
- [x] 2. Add `automojo-interop-aws` and `boto3` to `pyproject.toml`.
- [x] 3. Declare `AwsValidationError`, `AwsConflictError`, `AwsCapacityError`,
  `ConfirmationRequiredError` in `awserrors.py`.

## Resolver and Translator

- [x] 4. Implement `AwsResolver.image_to_ami(family, version, arch)` against
  `ec2.describe_images` using owner+name-pattern lookups for Ubuntu, Debian, Amazon
  Linux, RHEL.
- [x] 5. Implement `AwsResolver.size_to_instance_type(size_hint)` mapping the
  neutral size profile to a default instance family.
- [x] 6. Implement `AwsResolver.accelerator_to_instance_type(accel_spec)` consulting
  the `CloudAcceleratorCatalog` and validating EFA support when interconnect is
  requested.
- [x] 7. Implement `AwsTagTranslator.to_aws(neutral_tags)` and
  `AwsTagTranslator.from_aws(aws_tags)` with a round-trip identity contract.

## Validate

- [x] 8. Implement `AwsCloudProvisioner.validate(spec, aspects)` that walks every
  resource and dispatches to per-kind validators.
- [x] 9. Per-kind validators reject `CloudObjectBucket` with no region,
  `CloudSharedFilesystem(kind=WEKA)`, `CloudInterconnect(kind=INFINIBAND_*)`,
  and tag values exceeding 256 chars.
- [x] 10. EFA validator rejects requests targeting non-EFA-capable instance
  families.

## Plan

- [x] 11. Implement `AwsPlanBuilder.plan(spec, aspects)` calling read-before-create
  for every resource and emitting `PlanAction` entries.
- [x] 12. Implement drift detection for SG ingress/egress, instance tags, and
  volume size/type.
- [ ] 13. Emit `DELETE` actions for run-id-tagged resources that disappeared from
  the spec.  (Deferred: owned-orphan scan during plan is implementation-pending;
  destroy still cleans by tag.)

## Apply

- [x] 14. Implement `AwsApplyStages.apply_networking` (VPC, subnets, IGW, route
  tables, SGs, keypairs) in dependency order.
- [x] 15. Implement `AwsApplyStages.apply_compute` (instances, volumes,
  attachments) including cluster placement group + EFA ENI when
  `CloudInterconnect(kind=EFA)`.
- [x] 16. Implement `AwsApplyStages.apply_dns_and_storage` (S3, Route53, FSx
  attach).
- [x] 17. Wire `AwsCloudInitRenderer` into `run_instances` so `vpn_join` produces
  the `tailscale up` / Twingate connector snippet documented in
  [vpn-join-spec](../vpn-join-spec/design.md).
- [ ] 18. Persist the run inventory to
  `.output/provisioning/<runid>/aws-inventory.json` after each stage.  (Deferred
  to engine integration; the venue exposes ``inventory()`` for the engine's
  state store to consume.)
- [x] 19. Refuse to apply DELETE actions unless `aspects.confirm is True`.

## Destroy

- [x] 20. Implement `AwsDestroyStages.destroy(spec, aspects)` reversing the apply
  order.
- [x] 21. Call `IVPNControlPlane.delete_device` for each instance carrying
  `vpn_join` before EC2 termination is finalised.
- [x] 22. Treat already-absent resources as success.

## Inventory

- [x] 23. Implement `AwsInventory.list_run(spec, aspects)` returning
  `ProvisionedResource` records with public, private, and overlay addresses.

## Property tests (hypothesis)

- [x] 24. `test_apply_idempotent` — generate a spec, apply against
  `MockAwsClient`, re-apply, assert zero mutating calls on the second pass.
- [x] 25. `test_destroy_is_inverse_of_apply` — apply then destroy, assert mock
  account inventory is empty.
- [x] 26. `test_tag_round_trip_identity` —
  `from_aws(to_aws(neutral_tags)) == neutral_tags` for every generated tag set
  within AWS limits.
- [x] 27. `test_efa_validation_table` — every EFA-supporting family resolves to a
  cluster placement group + EFA ENI; every non-EFA family raises
  `AwsValidationError`.
- [x] 28. `test_accelerator_resolver_table` — every neutral accelerator name with a
  defined AWS SKU resolves; every unknown name raises.

## Integration tests (gated)

- [ ] 29. `RUN_LIVE_AWS=1` end-to-end: stand up a single t3.micro in an isolated
  VPC, attach a tag, re-apply, destroy.  Excluded from CI by default.

## Documentation

- [ ] 30. Author `provisioning/venues/aws/README.md` linking to this spec, the
  resource model, lifecycle, vpn-join, and the AWS interop client.
