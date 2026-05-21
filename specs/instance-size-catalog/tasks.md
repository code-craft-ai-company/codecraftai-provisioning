# Tasks

- [x] 1. Create `instancesizes.yaml` data file next to `accelerators.yaml`.
  - Define the neutral token vocabulary (`<family>.<size>`).
  - Populate `venue_skus` with real, plausible SKUs per cloud venue.

- [x] 2. Create `CloudInstanceSizeCatalogEntry` (`SchemaObject`) validating token
  shape, positive `vcpu`/`memory_gb`, and the `venue_skus` map.

- [x] 3. Create `CloudInstanceSizeCatalog` — line-marking loader, forward/reverse
  indexes, load-time uniqueness + injectivity invariants.
  - `resolve` returns `None` for unrecognised tokens (passthrough signal).
  - `supported_venues`, `vcpu`, `memory_gb`, `inverse_lookup`, `is_known_token`.
  - Lazy thread-safe singleton + `AUTOMOJO_INSTANCE_SIZE_CATALOG` override +
    `reset_default_instance_size_catalog()`.

- [x] 4. Fix the `CloudInstance.size` docstring to be honest about neutral tokens
  vs venue-native passthrough; keep the field type `str`.

- [x] 5. Wire the catalog into every cloud-venue size resolver (aws, azure, gcp,
  oracle, digitalocean, hetzner, linode, equinix_metal, vultr, crusoe, nebius,
  lambdalabs) — translate neutral tokens, pass native strings through unchanged.

- [x] 6. Add `test_instance_size_catalog.py` — loader unit tests + hypothesis
  property tests (totality, injectivity, round-trip, unknown → None).

- [x] 7. Add `test_instance_size_resolver_wiring.py` — per-venue tests proving a
  neutral token resolves and a native string passes through.
