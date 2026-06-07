# Design

## Overview

The accelerator catalog is a YAML data file plus a thin Python loader.  The plan's
§7.6 decision is binding: scatter accelerator → SKU knowledge across venue resolvers
and it will drift; concentrate it in one file and a one-line PR adds a new GPU.

The loader is a small immutable class.  After load it answers four questions:

- Given a neutral name and a venue, what SKU?
- Given a venue and an SKU, what neutral name?
- What venues support this neutral name?
- What is the full set of entries?

Property tests prove totality, injectivity, and round-trip — the three invariants that
make the data file safe to edit without breaking anything downstream.

---

## Architecture

```
   accelerators.yaml (packaged data file)
            │
            ▼
   CloudAcceleratorCatalog._load_from_path()
            │
            ▼
   List[CloudAcceleratorCatalogEntry]
            │
            ├──► resolve(neutral_name, venue) -> sku
            ├──► neutral_name(venue, sku) -> neutral_name
            ├──► supported_venues(neutral_name) -> List[str]
            └──► entries() -> List[entry]

   default_accelerator_catalog() ──► process-wide singleton
   from_path(path)               ──► test override
   CCAI_ACCELERATOR_CATALOG  ──► env-var override
```

---

## Data Model

```python
class CloudAcceleratorCatalogEntry(SchemaObject):
    neutral_name: str
    kind: Literal["GPU", "TPU", "IPU", "ASIC"]
    memory_gb: int
    interconnect: Literal["NONE", "PCIE", "NVLINK", "NVSWITCH", "INFINITY_FABRIC"]
    venue_skus: Dict[str, str]              # venue -> sku string
    default: bool = False


class CloudAcceleratorCatalog:
    def __init__(self, *, entries: List[CloudAcceleratorCatalogEntry]) -> None: ...

    @classmethod
    def from_path(cls, *, path: str) -> "CloudAcceleratorCatalog": ...

    def resolve(self, *, neutral_name: str, venue: str) -> str: ...
    def neutral_name(self, *, venue: str, sku: str) -> str: ...
    def supported_venues(self, *, neutral_name: str) -> List[str]: ...
    def entries(self) -> List[CloudAcceleratorCatalogEntry]: ...


def default_accelerator_catalog() -> CloudAcceleratorCatalog: ...
```

---

## YAML File Shape

```yaml
# accelerators.yaml
version: 1
entries:
  - neutral_name: H100_SXM
    kind: GPU
    memory_gb: 80
    interconnect: NVSWITCH
    venue_skus:
      aws: p5.48xlarge
      azure: Standard_ND96isr_H100_v5
      gcp: a3-highgpu-8g
      crusoe: h100-80gb-sxm5.8x
      coreweave: gd-8xh100ib-i128
    default: true

  - neutral_name: H200_NVL
    kind: GPU
    memory_gb: 141
    interconnect: NVLINK
    venue_skus:
      aws: p5e.48xlarge
      azure: Standard_ND96isr_H200_v5
    default: true

  - neutral_name: A100_80G_SXM
    kind: GPU
    memory_gb: 80
    interconnect: NVSWITCH
    venue_skus:
      aws: p4de.24xlarge
      azure: Standard_ND96amsr_A100_v4
      gcp: a2-ultragpu-8g
      oracle: BM.GPU.A100-v2.8

  # ... B200_SXM, A100_40G_PCIE, L40S, L4, GH200, MI300X, MI250X,
  #     TPU_V5P, TPU_V5E entries follow the same shape
```

The loader validates against `codecraftai-configuration`'s `SchemaObject` machinery.
Each entry's `venue_skus` mapping is keyed by the **provisioning venue name** (the
same string a `CloudVenue` uses), and the values are arbitrary venue-side strings.

---

## Module Layout

```
source/packages/ccai/provisioning/model/cloud/
├── accelerators.yaml                       # packaged data file
├── cloudacceleratorcatalog.py              # loader + lookup class
└── cloudacceleratorcatalogentry.py         # SchemaObject entry
```

Package data declaration in `pyproject.toml` includes `accelerators.yaml` as
distribution data.

---

## Resolution Algorithm

`resolve(neutral_name, venue)`:

1. Look up the entry by `neutral_name`; raise `SchemaSemanticError` if missing,
   listing all known neutral names.
2. Look up `venue` in `entry.venue_skus`; raise `SchemaSemanticError` if absent,
   listing the supporting venues from `supported_venues()`.
3. Return the SKU string.

`neutral_name(venue, sku)`:

1. Walk entries; for any whose `venue_skus[venue] == sku`, return the entry's
   `neutral_name`.
2. Raise `SchemaSemanticError` if no match.

Injectivity is enforced at *load time*, not at resolve-time: the loader builds the
reverse map per venue and rejects the catalog if any `(venue, sku)` collides across
two different `neutral_name`s.

---

## Concurrency

The catalog is immutable after construction.  All accessors are pure.  The default
singleton is built once under a module-level lock; thereafter readers do not lock.

---

## See Also

- [accelerator-and-interconnect-model](../accelerator-and-interconnect-model/design.md)
  — `CloudAcceleratorSpec` consumes the catalog for venue resolution.
- [cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md) — calls
  `resolve` during `validate` and `plan`.
- [workload-venue-model](../workload-venue-model/design.md) — `WorkloadCluster` node
  pools consume the catalog for K8s GPU resource hint translation.

---

## Testing Strategy

- **Unit tests** — load the packaged catalog; assert known entries exist with
  expected fields; verify reverse lookup; verify environment-variable override path.
- **Negative tests** — load deliberately malformed YAML; assert `ConfigurationError`
  with line numbers.  Load a catalog with a deliberate `(venue, sku)` collision and
  assert load-time rejection.
- **Property tests (`hypothesis`) ⊙:**
  - **Totality:** for every entry and every venue in its `venue_skus`,
    `resolve(...)` returns the recorded SKU.
  - **Injectivity:** per venue, the reverse map is bijective on its domain.
  - **Round-trip:** `neutral_name(resolve(...)) == neutral_name` for every
    `(entry, venue)`.
  - **Unknown rejection:** for any synthesised `(neutral_name, venue)` outside the
    catalog support set, `resolve` raises `SchemaSemanticError` (and only that type).
- Generators use `hypothesis.strategies.sampled_from(catalog.entries())` for the
  positive direction and `text()` for the negative direction.
