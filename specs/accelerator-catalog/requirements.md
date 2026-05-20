# Requirements

## Introduction

The accelerator catalog is the single source of truth for the mapping between
**neutral accelerator names** (`"H100_SXM"`, `"H200_NVL"`, `"B200_SXM"`, `"MI300X"`,
`"L40S"`, `"GH200"`, `"TPU_V5P"`, etc.) and the **venue-specific SKUs** that realise
them.  Per the §7.6 plan decision, the catalog lives as a YAML data file
(`accelerators.yaml`) loaded by a `CloudAcceleratorCatalog` class.

Adding a new GPU SKU is then a single-file, single-PR change — no Python code edits in
any venue-resolver class.  This is the explicit usability-versus-correctness tradeoff
the plan calls out: scatter resolvers across venues and they will drift; centralise
the data and consumers can audit it in one place.

The catalog has three algebraic properties that property tests enforce:

- **Totality** — every neutral name listed as supported by a venue MUST resolve on
  that venue.
- **Injectivity** — within one venue, no two neutral names map to the same SKU
  (collisions would silently route requests to wrong hardware).
- **Round-trip** — `neutral → venue_sku → neutral` is the identity for every entry.

---

## Requirements

### Requirement 1: YAML Catalog File

**User Story:** As a maintainer, I want to add a new GPU SKU by editing one YAML
file.

#### Acceptance Criteria

1. THE SYSTEM SHALL include
   `source/packages/automojo/provisioning/model/cloud/accelerators.yaml` as a
   distributed data file in the package.
2. THE SYSTEM SHALL define each entry with the fields:
   `neutral_name`, `kind`, `memory_gb`, `interconnect`, `venue_skus` (mapping of
   venue name to SKU string).
3. THE SYSTEM SHALL ship with at minimum the v1 entries: `H100_SXM`, `H100_PCIE`,
   `H200_SXM`, `H200_NVL`, `B200_SXM`, `A100_80G_SXM`, `A100_40G_PCIE`, `L40S`,
   `L4`, `GH200`, `MI300X`, `MI250X`, `TPU_V5P`, `TPU_V5E`.
4. WHEN the YAML file is malformed or any entry violates the schema THE SYSTEM SHALL
   raise `ConfigurationError` at load time with the offending entry identified by
   line number.

---

### Requirement 2: Catalog Loader Class

**User Story:** As a venue-provisioner author, I want a single Python API to resolve
neutral names to venue SKUs.

#### Acceptance Criteria

1. THE SYSTEM SHALL expose `CloudAcceleratorCatalog` with:
   - `resolve(*, neutral_name: str, venue: str) -> str`
   - `neutral_name(*, venue: str, sku: str) -> str` (reverse lookup)
   - `supported_venues(*, neutral_name: str) -> List[str]`
   - `entries() -> List[CloudAcceleratorCatalogEntry]`
2. WHEN `resolve` is called with a `neutral_name` not in the catalog THE SYSTEM SHALL
   raise `SchemaSemanticError`.
3. WHEN `resolve` is called with a `venue` that does not list support for that
   neutral name THE SYSTEM SHALL raise `SchemaSemanticError`.
4. THE SYSTEM SHALL be safe to call concurrently from multiple threads after load.

---

### Requirement 3: Singleton-Style Access

**User Story:** As a consumer, I want a single shared catalog instance so reloads
and overrides are explicit, not accidental.

#### Acceptance Criteria

1. THE SYSTEM SHALL expose `default_accelerator_catalog() -> CloudAcceleratorCatalog`
   returning a process-wide singleton loaded from the packaged YAML.
2. THE SYSTEM SHALL expose `CloudAcceleratorCatalog.from_path(*, path: str)` for
   tests and out-of-tree overrides.
3. WHEN the catalog file is overridden via the environment variable
   `AUTOMOJO_ACCELERATOR_CATALOG` THE SYSTEM SHALL load from the indicated path on
   first access.

---

### Requirement 4: Neutral-to-Venue Resolution

**User Story:** As a venue provisioner, I want to translate a `CloudAcceleratorSpec`
into a venue-specific compute SKU.

#### Acceptance Criteria

1. WHEN a venue provisioner calls `resolve(neutral_name="H100_SXM", venue="aws")` THE
   SYSTEM SHALL return the AWS instance SKU string (e.g. `"p5.48xlarge"`).
2. WHEN a `count` does not match the SKU's accelerator count THE SYSTEM SHALL raise
   `SchemaSemanticError` indicating the closest valid count.
3. WHEN multiple SKUs satisfy the neutral spec on a venue THE SYSTEM SHALL prefer
   the entry marked `default: true` in the YAML; if none, the first listed.

---

### Requirement 5: Property Test Invariants ⊙

**User Story:** As a maintainer, I want catalog invariants enforced automatically.

#### Acceptance Criteria

1. THE SYSTEM SHALL include property tests asserting:
   - **Totality** — for every entry `e` and every venue `v` in `e.venue_skus`,
     `resolve(neutral_name=e.neutral_name, venue=v)` returns the expected SKU.
   - **Injectivity** — for every venue `v`, the map
     `{e.neutral_name: e.venue_skus[v] for e in catalog if v in e.venue_skus}`
     has no duplicate values.
   - **Round-trip** — for every entry `e` and every venue `v` in `e.venue_skus`,
     `neutral_name(venue=v, sku=resolve(neutral_name=e.neutral_name, venue=v))`
     returns `e.neutral_name`.
2. THE SYSTEM SHALL include a property test that generates random `(venue,
   neutral_name)` requests; for any combination not in the catalog support set,
   `SchemaSemanticError` is raised — and never any other exception type.
