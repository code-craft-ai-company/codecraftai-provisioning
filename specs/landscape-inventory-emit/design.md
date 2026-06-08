# Design

## Overview

The landscape-inventory-emit module produces a `landscape.yaml`-compatible block from
the per-venue inventory produced by `provisioner.inventory(...)`.  The emit step is
the final stage of the provisioning pipeline and is what makes a freshly-provisioned
environment immediately usable by `codecraftai-landscaping` without any manual file
authoring.

The module is small: one converter class that walks the inventory, optionally calls
the VPN control plane for overlay addresses, and emits a YAML document that round-
trips through landscape's own loader.  All schema details that landscape cares about
live in `codecraftai-landscaping/specs/landscape-yaml-schema`; this module is the
**writer**, not the schema definition.

---

## Architecture

```
   per-venue inventory
   Dict[venue_name, List[ProvisionedResource]]
              │
              │ filter kind == "instance"
              ▼
   instance ProvisionedResources
              │
              │ for each:
              │   collect public + private from attributes
              │   if vpn_join:
              │     query IVPNControlPlane for overlay
              ▼
   landscape device entries (DeviceAddressSet per host)
              │
              │ + venues block
              │ + vpn block (when any vpn_join present)
              │ + groups (from spec)
              ▼
   landscape.yaml document
              │
              ▼
   <runid>/landscape.yaml (atomic write)
```

---

## Data Model

```python
class LandscapeEmitter:
    def __init__(self, *, spec: PipelineSpec,
                 inventory: Dict[str, List[ProvisionedResource]],
                 control_planes: Dict[str, IVPNControlPlane]) -> None: ...

    def emit(self, *, aspects: Aspects) -> Dict[str, Any]:
        """
            Build the landscape.yaml dict.

            :param aspects: aspects controlling overlay-query timeouts.
            :returns: a dict ready to be yaml.safe_dump'd.
        """
        ...


class DeviceAddressBlock(SchemaObject):
    public: Optional[str]
    private: Optional[str]
    overlay: Optional[Dict[str, str]]   # {provider, address, magic_dns}
```

---

## Output Shape

Sketch:

```yaml
apod:
  name: <from spec>
  devices:
    - name: <instance.name>
      venue: <venue_name>
      group: <group from spec>
      addresses:
        public: 203.0.113.10
        private: 10.0.1.10
        overlay:
          provider: tailscale
          address: 100.64.0.7
          magic_dns: web-01.tailnet-xyz.ts.net
      tags:
        - role: web
        - env: ci

environment:
  venues:
    - name: aws-us-east
      kind: aws
      region: us-east-1

vpn:
  providers:
    - name: lab-tailnet
      kind: tailscale
      credential_ref: tailscale-oauth-lab
      default_tags: ["tag:lab"]
```

---

## Overlay Resolution

For each instance with `vpn_join`:

1. Look up the control plane registered for `vpn_join.provider`.
2. Call `control_plane.list_devices(aspects=...)` once, then look up by hostname.
3. Cache results per emit to avoid N API calls for N instances on the same provider.
4. On failure, log a warning and omit the overlay block; do not fail the emit.

---

## Module Layout

```
source/packages/ccai/provisioning/landscape/
├── landscapeemitter.py
├── deviceaddressblock.py
└── overlayaddressresolver.py
```

---

## See Also

- [provisioning-engine-pipeline](../provisioning-engine-pipeline/design.md) — invokes
  the emitter as the final stage.
- [provisioning-state-persistence](../provisioning-state-persistence/design.md) —
  writes `landscape.yaml` atomically.
- [cloud-resource-model](../cloud-resource-model/design.md) — source of instance
  attributes.
- [vpn-join-spec](../vpn-join-spec/design.md) — drives overlay resolution.
- `codecraftai-interfaces/specs/address-plane-types` — `DeviceAddressSet` shape that
  landscape consumes.
- `codecraftai-interfaces/specs/vpn-control-plane-protocol` — `list_devices`.

---

## Testing Strategy

- **Unit tests** — emit from a fixture inventory; assert the device entries' shapes
  and tag/group preservation.
- **Empty-inventory test** — assert a valid (empty) `landscape.yaml` is still
  produced.
- **Public-IP-off test** — assert `public` is *omitted* (not null) when the
  instance has no public address.
- **VPN-overlay test** — fake `IVPNControlPlane.list_devices` returns known
  mappings; assert overlay block present.
- **Overlay-failure test** — fake control plane raises; emitter still produces
  device entries and logs a warning.
- **Round-trip test** — emitted file loaded by `codecraftai-landscaping` test loader
  (or a stub matching the schema) without warnings.
