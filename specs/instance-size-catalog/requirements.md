# Requirements

## Introduction

The instance-size catalog is the single source of truth for the mapping between
**neutral instance-size tokens** (`general.small`, `general.large`,
`compute.xlarge`, `memory.large`, etc.) and the **venue-native size SKUs** that
realise them (AWS `m5.xlarge`, Hetzner `cx42`, GCP `e2-standard-4`, ...).

Before this catalog, `CloudInstance.size` was documented "venue-neutral" but every
venue resolver expected a venue-native string, so a multi-venue spec had to write a
different `size` per venue.  The catalog lets users write ONE neutral size
vocabulary; venue resolvers translate it.  Power users may still pass a venue-native
string directly — an unrecognised token resolves to `None`, signalling passthrough.

This catalog covers **CPU/RAM instance shapes only**.  GPU/accelerator sizing lives
in the accelerator catalog (`accelerators.yaml`) and is not duplicated here.

The catalog mirrors the accelerator-catalog pattern: a YAML data file
(`instancesizes.yaml`) loaded by a `CloudInstanceSizeCatalog` class.  Adding a venue
SKU is a single-file, single-PR change.

Algebraic properties property tests enforce:

- **Totality** — every token resolves on every venue it lists.
- **Injectivity** — within one venue, no two tokens map to the same SKU.
- **Round-trip** — `token → venue_sku → token` is the identity for every entry.
- **Unknown passthrough** — an unrecognised token resolves to `None`.

---

## Requirements

### Requirement 1: YAML Catalog File

**User Story:** As a maintainer, I want to add a venue SKU by editing one YAML file.

#### Acceptance Criteria

1. THE SYSTEM SHALL load `instancesizes.yaml` packaged alongside the catalog module.
2. Each entry SHALL carry `token`, `vcpu`, `memory_gb`, and a `venue_skus` map.
3. The `token` SHALL be of the form `<family>.<size>` where family is one of
   `general`, `compute`, `memory` and size is one of `small`, `medium`, `large`,
   `xlarge`, `2xlarge`.
4. WHEN the YAML is malformed or an entry is invalid THEN THE SYSTEM SHALL raise
   `ConfigurationError` with a 1-based source line number.

### Requirement 2: Lookup API

**User Story:** As a venue resolver, I want to translate a neutral token to a SKU.

#### Acceptance Criteria

1. `resolve(token, venue)` SHALL return the native SKU for a recognised token.
2. WHEN `token` is not a recognised neutral token THEN `resolve` SHALL return `None`.
3. WHEN `token` is recognised but the venue is not listed THEN `resolve` SHALL raise
   `SchemaSemanticError`.
4. THE SYSTEM SHALL expose `supported_venues(token)`, `vcpu(token)`,
   `memory_gb(token)`, `inverse_lookup(venue_sku, venue)` and `is_known_token(token)`.

### Requirement 3: Singleton + Override

#### Acceptance Criteria

1. THE SYSTEM SHALL expose a process-wide default singleton via
   `default_instance_size_catalog()` / `CloudInstanceSizeCatalog.default()`.
2. THE SYSTEM SHALL honour the `CCAI_INSTANCE_SIZE_CATALOG` env-var override.
3. THE SYSTEM SHALL expose `reset_default_instance_size_catalog()` for test isolation.

### Requirement 4: Venue Resolver Wiring

#### Acceptance Criteria

1. Every cloud-venue size resolver SHALL translate a neutral token via the catalog
   before its existing native-string logic.
2. A venue-native size string SHALL pass through resolvers unchanged.
