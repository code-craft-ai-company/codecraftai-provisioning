# Implementation Plan — Cloud Resource Model

## Model Classes

- [x] 1. Create `cloudnetwork.py` — `CloudNetwork(SchemaObject)` with CIDR validation
- [x] 2. Create `cloudsubnet.py` — `CloudSubnet(SchemaObject)` referencing network by name
- [x] 3. Create `cloudingressrule.py` — `CloudIngressRule(SchemaObject)` with port-range check
- [x] 4. Create `cloudegressrule.py` — `CloudEgressRule(SchemaObject)` symmetric to ingress
- [x] 5. Create `cloudsecuritygroup.py` — `CloudSecurityGroup(SchemaObject)`
- [x] 6. Create `cloudkeypair.py` — `CloudKeyPair(SchemaObject)`
- [x] 7. Create `cloudimage.py` — `CloudImage(SchemaObject)`
- [x] 8. Create `cloudinstance.py` — `CloudInstance(SchemaObject)` with optional slots
- [x] 9. Create `cloudstoragevolume.py` — `CloudStorageVolume(SchemaObject)`
- [x] 10. Create `cloudobjectbucket.py` — `CloudObjectBucket(SchemaObject)`
- [x] 11. Create `cloudloadbalancer.py` — `CloudLoadBalancer(SchemaObject)`
- [x] 12. Create `clouddnsrecord.py` — `CloudDnsRecord(SchemaObject)`

## CloudResourceProfile Discriminator

- [x] 13. Extend `cloudresourceprofile.py` — add typed `kind` literal
- [x] 14. Implement per-kind payload dispatch to the matching model class
- [x] 15. Raise `SchemaValidationError` for unknown `kind`

## Validation Helpers

- [x] 16. Add `_validate_cidr(value: str) -> None` shared helper
- [x] 17. Add `_validate_name(value: str, max_len: int = 63) -> None`
- [x] 18. Add `_validate_port_range(from_port: int, to_port: int) -> None`

## Tests — Examples

- [x] 19. `test_cloudnetwork_roundtrip`
- [x] 20. `test_cloudnetwork_rejects_bad_cidr`
- [x] 21. `test_cloudsubnet_roundtrip`
- [x] 22. `test_security_group_with_rules_roundtrip`
- [x] 23. `test_ingress_rule_rejects_inverted_port_range`
- [x] 24. `test_ingress_rule_rejects_no_source`
- [x] 25. `test_cloudinstance_optional_slots_default_none`
- [x] 26. `test_cloudinstance_twingate_non_connector_fails_semantic`
- [x] 27. `test_dns_record_rejects_unknown_record_type`
- [x] 28. `test_resource_profile_dispatches_to_correct_class`

## Tests — Property (hypothesis) ⊙

- [x] 29. `test_property_subnet_contained_in_network`
- [x] 30. `test_property_sibling_subnets_no_overlap`
- [x] 31. `test_property_ingress_egress_pair_roundtrip`
- [x] 32. `test_property_resource_profile_dispatch_total`
- [x] 33. `test_property_all_model_classes_roundtrip`

## Documentation

- [ ] 34. Add usage examples to module docstrings (deferred: documentation not yet authored)
- [ ] 35. Cross-link to `cloud-provisioner-lifecycle` in `See Also` (deferred: documentation cross-link not yet authored)
