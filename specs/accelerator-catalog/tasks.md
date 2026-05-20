# Implementation Plan — Accelerator Catalog

## Data File

- [x] 1. Author `accelerators.yaml` with v1 entries (H100, H200, B200, A100, L40S, L4,
        GH200, MI300X, MI250X, TPU_V5P, TPU_V5E)
- [x] 2. Declare `accelerators.yaml` as package data in `pyproject.toml`
- [x] 3. Document the file format in the file's header comments

## Loader Classes

- [x] 4. Create `cloudacceleratorcatalogentry.py` — `SchemaObject` entry class
- [x] 5. Create `cloudacceleratorcatalog.py` — loader + lookup class
- [x] 6. Implement `from_path(path)` classmethod
- [x] 7. Implement load-time injectivity check (reject duplicate SKUs per venue)
- [x] 8. Implement `resolve(neutral_name, venue) -> sku`
- [x] 9. Implement `neutral_name(venue, sku) -> neutral_name`
- [x] 10. Implement `supported_venues(neutral_name) -> List[str]`
- [x] 11. Implement `entries() -> List[entry]`

## Singleton + Overrides

- [x] 12. Implement `default_accelerator_catalog()` with thread-safe lazy init
- [x] 13. Implement `AUTOMOJO_ACCELERATOR_CATALOG` env-var override
- [x] 14. Document override precedence: env-var > packaged file

## Error Surfaces

- [x] 15. Raise `ConfigurationError` on malformed YAML or schema violation
- [x] 16. Raise `SchemaSemanticError` for missing entries / unsupported venues
- [x] 17. Include line numbers in load-time errors

## Tests — Examples

- [x] 18. `test_default_catalog_loads_v1_entries`
- [x] 19. `test_resolve_returns_expected_sku`
- [x] 20. `test_resolve_raises_for_unknown_neutral_name`
- [x] 21. `test_resolve_raises_for_unsupported_venue`
- [x] 22. `test_neutral_name_reverse_lookup`
- [x] 23. `test_supported_venues_returns_all_listed_venues`
- [x] 24. `test_loader_rejects_duplicate_sku_within_venue`
- [x] 25. `test_env_var_override_loads_alternate_catalog`

## Tests — Property (hypothesis) ⊙

- [x] 26. `test_property_catalog_totality`
- [x] 27. `test_property_catalog_injectivity_per_venue`
- [x] 28. `test_property_catalog_roundtrip_identity`
- [x] 29. `test_property_unknown_request_raises_semantic_error_only`

## Documentation

- [ ] 30. Document the §7.6 single-file-PR addition workflow (deferred: documentation not yet authored)
- [ ] 31. Cross-link `accelerator-and-interconnect-model` (deferred: documentation cross-link not yet authored)
