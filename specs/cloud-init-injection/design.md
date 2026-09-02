# Design

## Overview

The cloud-init-injection module is the venue-shared payload renderer.  It exists for
exactly one reason: the same bootstrap behaviour (install Tailscale or Twingate, bring
up the link with a freshly minted auth key, hostname, and tags) is needed on every
venue, and reimplementing it in nine venue plugins would guarantee drift.  The plan's
§8 commitments require the renderer to be one module shared by all.

The renderer accepts a `VPNJoinSpec`, a minted auth-key string, a rendered hostname,
and the target image family.  It produces a venue-agnostic cloud-init document
fragment that the venue plugin merges with whatever else it wants to ship in
`user_data`.  Two thin wrappers adapt the same fragment into Azure CSE and vSphere
guest-customization shapes.

Secret quoting is the load-bearing safety property here.  The cloud-init log file is
world-readable on more than one venue; even with ephemeral auth keys the rendered
payload must not let a tag value or hostname injection escape into the shell.

---

## Architecture

```
   VPNJoinSpec  +  authkey  +  rendered_hostname  +  image_family
                            │
                            ▼
              render_cloud_init(...) ──► Dict (cloud-init YAML fragment)
                            │
            ┌───────────────┴────────────────┐
            ▼                                ▼
   render_azure_cse(...)         render_vsphere_guest_customization(...)
   (PowerShell on Windows,        (userData for Linux,
    bash on Linux)                 sysprep RunOnceCommands on Windows)
            │                                │
            ▼                                ▼
   Azure CustomScript Extension   vSphere VmGuestCustomizationSpec
```

---

## Cloud-Init Fragment Shape

```yaml
# Result of render_cloud_init for tailscale + ubuntu
write_files:
  - path: /etc/tailscale/authkey
    owner: root:root
    permissions: '0400'
    content: |
      tskey-auth-xxxxxxxxxxxxx

  - path: /etc/tailscale/bringup.sh
    owner: root:root
    permissions: '0700'
    content: |
      #!/bin/bash
      set -euo pipefail
      AUTHKEY="$(cat /etc/tailscale/authkey)"
      HOST="web-01"
      TAGS="tag:lab,tag:web"
      tailscale up \
        --auth-key="${AUTHKEY}" \
        --hostname="${HOST}" \
        --advertise-tags="${TAGS}"

runcmd:
  - [ sh, -c, "curl -fsSL https://tailscale.com/install.sh | sh" ]
  - [ /etc/tailscale/bringup.sh ]
```

The auth key never appears as a YAML scalar that the shell sees directly; it lives in
a root-only file that the bring-up script reads.  Hostname and tags are interpolated
into the script's shell context via assigned variables and quoted at the
`tailscale up` invocation.

---

## Data Model

```python
def render_cloud_init(*, spec: VPNJoinSpec,
                      authkey: str,
                      rendered_hostname: str,
                      image_family: str) -> Dict[str, Any]: ...


def render_azure_cse(*, spec: VPNJoinSpec,
                     authkey: str,
                     rendered_hostname: str,
                     image_family: str) -> Dict[str, Any]: ...


def render_vsphere_guest_customization(*, spec: VPNJoinSpec,
                                       authkey: str,
                                       rendered_hostname: str,
                                       image_family: str) -> Dict[str, Any]: ...


class CloudInitRendererError(Exception):
    """Raised when an unsupported image family is requested."""


SUPPORTED_LINUX_FAMILIES = {"ubuntu", "debian", "rhel", "fedora", "amazonlinux"}
SUPPORTED_WINDOWS_FAMILIES = {"windows-server"}
```

---

## Twingate Branch

For `spec.provider == "twingate"` the renderer:

1. Installs the `twingate` package via the Twingate apt or yum repo.
2. Writes `/etc/twingate/connector.conf` with the connector token (analogous to
   auth-key write_files block, mode 0400, root-only).
3. Enables the `twingate-connector` systemd service.
4. Honours `spec.advertise_routes` by emitting connector resource declarations.

The Twingate connector does not give the host an overlay IP — the renderer reflects
this by emitting NO additional hostname registration step (per §3 plan asymmetry).

---

## Module Layout

```
source/packages/ccai/provisioning/cloudinit/
├── vpncloudinitrenderer.py        # render_cloud_init, render_azure_cse,
│                                  # render_vsphere_guest_customization
├── pythonenvcloudinitrenderer.py  # render_python_env_cloud_init (python-env-bootstrap)
├── cloudinitmerge.py              # merge_cloud_init_fragments
├── bootstraprenderer.py           # render_instance_cloud_init / render_instance_user_data
└── secretquoting.py               # shared quoting helpers
```

The VPN renderer was the only fragment producer when this spec was written;
`bootstraprenderer` now composes it with the Python-environment fragment (see
[python-env-bootstrap](../python-env-bootstrap/design.md)).  Venues SHOULD call
`render_instance_user_data` rather than `render_cloud_init` directly so new
fragments reach every venue without per-venue edits.

---

## See Also

- [vpn-join-spec](../vpn-join-spec/design.md) — defines `VPNJoinSpec` and the
  renderer contract.
- [python-env-bootstrap](../python-env-bootstrap/design.md) — the Python
  virtual-environment fragment merged alongside this one.
- [provisioning-engine-pipeline](../provisioning-engine-pipeline/design.md) —
  invokes the renderer during `BOOTSTRAP_VPN`.
- `codecraftai-credentials/specs/tailscale-credentials` — auth-key source.
- `codecraftai-credentials/specs/twingate-credentials` — connector token source.
- `codecraftai-interop-vsphere/specs/vsphere-guest-customization` — consumer of the
  vSphere wrapper.
- venue plugins (aws, azure, gcp, ...): each call the renderer at instance-create
  time.

---

## Testing Strategy

- **Unit tests** — render a known `VPNJoinSpec` for each supported image family;
  snapshot-assert the output YAML structure.
- **Tag-injection test** — render with a tag containing whitespace and shell
  metacharacters; assert the rendered shell parses safely.
- **Auth-key quoting test** — render with an auth key containing `$`, backticks,
  and quotes; assert the key reaches the daemon intact (simulated by parsing the
  rendered shell with `shlex`).
- **Image-family rejection test** — unsupported family raises
  `CloudInitRendererError`.
- **Property tests (`hypothesis`) ⊙:**
  - `cloud_init_yaml_validity_property` — for any spec, `yaml.safe_load(render)`
    succeeds.
  - `secret_appears_once_property` — auth key appears exactly once in the rendered
    document and only inside the `write_files.content` for the authkey file.
  - `tag_roundtrip_property` — tag values survive render→`yaml.safe_load`→assert
    equality.
  - `azure_cse_json_validity_property` — for any spec, `json.dumps(render_azure_cse)`
    succeeds and round-trips through `json.loads`.
