# Design

## Overview

`VPNJoinSpec` is a small typed data class plus a hostname renderer.  Every venue
provisioner consults it after compute has been created to inject the right install +
bring-up commands into the bootstrap payload (cloud-init, Azure CustomScript, vSphere
guest-customization).

The cloud-init **payload assembly** is shared across venues and lives in the
[cloud-init-injection](../cloud-init-injection/design.md) spec.  This spec defines the
data shape, the hostname renderer, and the *contract* for the cloud-init renderer that
the injection module implements.

The §5 plan decision pins auth-key handling to ephemeral, OAuth-minted, TTL ≤ 15 min;
the renderer accepts a freshly-minted string and never persists it.  The injection
module is responsible for quoting it in every shell position to defeat the "world-
readable cloud-init log" failure mode the plan calls out.

---

## Architecture

```
   spec author                  CloudInstance
        │                            │
        │ VPNJoinSpec(...)           │ .vpn_join
        └───────────┬────────────────┘
                    ▼
              VPNJoinSpec (SchemaObject)
                    │
   render_hostnames(template, contexts) ─► uniqueness + DNS-label check
                    │
                    ▼
        per-instance rendered hostname
                    │
   IVPNControlPlane.mint_authkey(...) ─► ephemeral auth key
                    │
                    ▼
        render_cloud_init(spec, authkey, hostname, image_family)
                    │
                    ▼
        cloud-init dict → cloud-init-injection module → venue user-data
```

---

## Data Model

```python
class VPNJoinSpec(SchemaObject):
    provider: Literal["tailscale", "twingate"]
    control_plane_credential: str                  # credential vault name
    advertise_tags: List[str]
    hostname_template: str
    ephemeral: bool = True
    preauthorized: bool = True
    advertise_routes: Optional[List[str]] = None   # CIDR strings
    exit_node: bool = False
    connector_only: bool = False                   # required True for twingate
```

### Renderer Functions

```python
def render_hostnames(*, template: str, contexts: List[Dict[str, Any]]) -> List[str]:
    """
        Render `template` against each `contexts` entry and return the list of
        rendered hostnames.  Raises SchemaSemanticError on unknown variables,
        invalid DNS labels, or duplicate rendered names.
    """


def render_cloud_init(*, spec: VPNJoinSpec, authkey: str,
                      rendered_hostname: str,
                      image_family: str) -> Dict[str, Any]:
    """
        Return a cloud-init document fragment that installs the VPN daemon (if
        needed) and brings the link up with the supplied auth key, hostname, and
        tags.  Auth key is always quoted; never appears unquoted in any shell
        position.
    """
```

### Validation Pipeline

```
  template ──► tokenise ──► substitute ──► normalise (lower, _→-) ──► RFC 1123 check
                                                                            │
   contexts[] ──► render each ──► collect ──► duplicate check ──► return list
```

DNS label validation uses a single compiled regex:

```python
_DNS_LABEL_RE = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")
```

---

## Module Layout

```
source/packages/ccai/provisioning/model/vpn/
├── __init__.py
├── vpnjoinspec.py          # VPNJoinSpec
└── hostnamerenderer.py     # render_hostnames + DNS-label helpers
```

Cloud-init rendering lives in:

```
source/packages/ccai/provisioning/cloudinit/
├── vpncloudinitrenderer.py # render_cloud_init
```

(See the [cloud-init-injection](../cloud-init-injection/design.md) spec for full
layout.)

---

## Auth Key Handling

The renderer never accepts a credential object directly — it accepts an
already-minted auth-key string.  Mint flow lives in the lifecycle layer:

1. `provisioner.apply(...)` looks up `spec.control_plane_credential` in the credential
   vault.
2. If the credential is a `TailscaleOAuthCredential`, an `IVPNControlPlane` instance
   mints a per-instance ephemeral, preauthorized, reusable=false key with TTL ≤ 15
   minutes (per §5 decision).
3. If the credential is already a `TailscaleAuthKeyCredential` (lab-only path), the
   raw key is used directly.
4. The minted/static key is passed to `render_cloud_init(authkey=...)` for the single
   instance being prepared.

The renderer logs the **fingerprint** of the key (first 6 chars + length) for
debuggability but never the full value.

---

## Quoting Rules

In the rendered `runcmd`, the auth key MUST appear as:

```
tailscale up --auth-key="${AUTHKEY}" --hostname="${HOST}" --advertise-tags="${TAGS}"
```

with `${AUTHKEY}` assigned via a `write_files` block that writes the key to a
root-only file (`/etc/tailscale/authkey`, mode `0400`) and `runcmd` reads it via a
shell `read` rather than interpolating it directly into the YAML.  This keeps the
key out of cloud-init's plaintext document representation in the venue's user-data
storage.

---

## See Also

- [cloud-init-injection](../cloud-init-injection/design.md) — payload assembly.
- [cloud-resource-model](../cloud-resource-model/design.md) — `CloudInstance.vpn_join`.
- [cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md) — runs the
  mint + render + inject flow.
- `codecraftai-interfaces/specs/vpn-control-plane-protocol` — `IVPNControlPlane.mint_authkey`.
- `codecraftai-credentials/specs/tailscale-credentials` — credential classes.

---

## Testing Strategy

- **Unit tests** — round-trip `VPNJoinSpec`; rejection cases for Twingate exit-node,
  Twingate non-connector, malformed advertise-routes, unknown template variable.
- **Renderer unit tests** — simple template renders, normalisation cases
  (`HOST_1` → `host-1`), explicit duplicate-collision case.
- **Property tests (`hypothesis`) ⊙:**
  - `template_and_index_strategy()` generates a template containing `{index}` and a
    population of N contexts; the property asserts uniqueness of rendered names.
  - `dns_label_property()` asserts every rendered name matches `_DNS_LABEL_RE`.
  - `cloud_init_yaml_property()` asserts `yaml.safe_load(rendered)` parses for any
    arbitrary `VPNJoinSpec`.
  - `authkey_quoting_property()` asserts the auth key, no matter what string is
    chosen, appears exactly once and only inside quoted shell positions or in the
    `write_files` body.
- All property tests run inside the `unittest` harness.
