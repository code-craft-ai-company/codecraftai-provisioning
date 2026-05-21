# Design

## Overview

The instance-size catalog mirrors the accelerator-catalog design: a YAML data file
plus an immutable, indexed loader class.  It centralises the neutral-token →
venue-native-SKU mapping for CPU/RAM instance shapes so consumers can audit it in
one place rather than scattering size tables across 12 venue resolvers.

## Data File: `instancesizes.yaml`

```yaml
version: 1
entries:
  - token: general.large
    vcpu: 4
    memory_gb: 16
    venue_skus:
      aws: m5.xlarge
      hetzner: cx42
      gcp: e2-standard-4
      ...
```

- `token` — `<family>.<size>`; families `general | compute | memory`; sizes
  `small | medium | large | xlarge | 2xlarge`.
- `vcpu`, `memory_gb` — neutral shape metadata (positive ints).
- `venue_skus` — map of venue name → native SKU.  A token omits venues with no good
  match.

Venue keys: `aws`, `azure`, `gcp`, `oracle`, `digitalocean`, `hetzner`, `linode`,
`equinix_metal`, `vultr`, `crusoe`, `nebius`, `lambdalabs`.

## Class: `CloudInstanceSizeCatalogEntry`

A `SchemaObject` validating `token` shape, positive `vcpu`/`memory_gb`, and a
non-empty `venue_skus` map of non-empty strings.

## Class: `CloudInstanceSizeCatalog`

```python
class CloudInstanceSizeCatalog:
    @classmethod
    def from_path(cls, *, path: str) -> "CloudInstanceSizeCatalog"
    @classmethod
    def default(cls) -> "CloudInstanceSizeCatalog"
    def entries(self) -> List[CloudInstanceSizeCatalogEntry]
    def is_known_token(self, *, token: str) -> bool
    def resolve(self, *, token: str, venue: str) -> Optional[str]
    def inverse_lookup(self, *, venue_sku: str, venue: str) -> str
    def supported_venues(self, *, token: str) -> List[str]
    def vcpu(self, *, token: str) -> int
    def memory_gb(self, *, token: str) -> int
```

Built once, indexed forward (`token → venue → sku`) and reverse
(`venue → sku → token`).  Load-time invariants: unique tokens, per-venue SKU
injectivity.  A `_LineMarkingSafeLoader` records source line numbers so load errors
point at the offending YAML line.

`resolve` returns `None` for an unrecognised token — the power-user passthrough
signal — and raises `SchemaSemanticError` only when a *recognised* token is not
published on the requested venue.

## Singleton

`default_instance_size_catalog()` lazily builds a thread-safe process-wide
singleton, honouring `AUTOMOJO_INSTANCE_SIZE_CATALOG`.
`reset_default_instance_size_catalog()` clears it for tests.

## Venue Resolver Wiring

Each cloud-venue size resolver prepends, at the top of its `size_to_*` method:

```python
size_catalog = CloudInstanceSizeCatalog.default()
native = size_catalog.resolve(token=size_hint, venue="<venue>")
effective = native if native is not None else size_hint
```

The existing native-string logic then proceeds with `effective`.  On-prem /
hypervisor venues (vsphere, hyperv, proxmox, nutanix, xcpng, libvirt) have no
native SKUs and are not in `venue_skus`; they retain their existing generic
hardware-size handling and are not wired.
