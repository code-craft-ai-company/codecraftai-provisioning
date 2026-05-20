# Implementation Plan — VPN Join Spec

## Data Class

- [x] 1. Create `vpnjoinspec.py` — `VPNJoinSpec(SchemaObject)` with all fields
- [x] 2. Validate `provider` literal membership
- [x] 3. Validate `connector_only=True` when provider is twingate
- [x] 4. Validate `exit_node=False` when provider is twingate
- [x] 5. Validate `advertise_routes` CIDR list when present

## Hostname Renderer

- [x] 6. Create `hostnamerenderer.py`
- [x] 7. Implement `render_hostnames(template, contexts) -> List[str]`
- [x] 8. Implement `_substitute_tokens(template, context) -> str`
- [x] 9. Implement `_normalise_label(value) -> str` (lower, `_`→`-`)
- [x] 10. Implement `_validate_dns_label(value) -> None` against `_DNS_LABEL_RE`
- [x] 11. Implement duplicate detection across the rendered list

## Cloud-Init Renderer Contract

- [x] 12. Declare `render_cloud_init` signature in `vpncloudinitrenderer.py`
- [x] 13. Implementation lives in `cloud-init-injection` spec; this spec only owns
        the function signature and contract
- [ ] 14. Document quoting rules in the function docstring (deferred: docstring quoting-rules section not yet authored)

## Credential Resolution

- [x] 15. Add lifecycle hook to resolve `control_plane_credential` from vault
- [x] 16. Verify credential class matches declared provider
- [x] 17. Raise `SchemaSemanticError` for missing or mismatched credential

## Tests — Examples

- [x] 18. `test_vpnjoinspec_roundtrip`
- [x] 19. `test_vpnjoinspec_rejects_twingate_non_connector`
- [x] 20. `test_vpnjoinspec_rejects_twingate_exit_node`
- [x] 21. `test_vpnjoinspec_rejects_bad_advertise_route_cidr`
- [x] 22. `test_render_hostnames_simple`
- [x] 23. `test_render_hostnames_rejects_unknown_variable`
- [x] 24. `test_render_hostnames_rejects_duplicate`
- [x] 25. `test_render_hostnames_normalises_underscore_and_case`

## Tests — Property (hypothesis) ⊙

- [x] 26. `test_property_render_hostnames_unique_when_index_in_template`
- [x] 27. `test_property_rendered_name_is_valid_dns_label`
- [x] 28. `test_property_cloud_init_is_valid_yaml_for_any_spec`
- [x] 29. `test_property_authkey_quoted_in_every_shell_position`

## Documentation

- [ ] 30. Cross-link `cloud-init-injection` from the cloud-init renderer contract (deferred: documentation cross-link not yet authored)
- [ ] 31. Document the §5 ephemeral-key-only default in the module docstring (deferred: module docstring §5 note not yet authored)
