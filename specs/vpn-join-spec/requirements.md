# Requirements

## Introduction

`VPNJoinSpec` is the data record attached to a `CloudInstance` to declare that the
instance should join a mesh VPN (Tailscale or Twingate) during provisioning.  The
provisioning engine uses it to render cloud-init / Custom Script Extension / vSphere
guest-customization payloads that install the daemon and bring the link up with the
right authentication, hostname, and tags.

Hostname rendering is non-trivial: the rendered hostname **must** be a valid DNS label
(RFC 1035 / 1123) **and** unique across the group of instances sharing the template,
because MagicDNS and Twingate FQDN resolution depend on it.  This spec requires
property-based testing of the rendering function.

This spec defines only the **data class** and the **renderer contract**.  Cloud-init
payload assembly (which incorporates the rendered values) lives in the
[cloud-init-injection](../cloud-init-injection/design.md) spec, which is shared across
every venue provisioner.

---

## Requirements

### Requirement 1: VPNJoinSpec Class

**User Story:** As a provisioning author, I want a single typed record that captures
everything a provisioner needs to join an instance to my mesh VPN.

#### Acceptance Criteria

1. THE SYSTEM SHALL expose `VPNJoinSpec(provider, control_plane_credential,
   advertise_tags, hostname_template, ephemeral: bool, preauthorized: bool,
   advertise_routes, exit_node: bool, connector_only: bool)` as a `SchemaObject`.
2. THE SYSTEM SHALL define `provider` as `Literal["tailscale", "twingate"]`.
3. WHEN `provider == "twingate"` and `connector_only` is `False` THE SYSTEM SHALL
   raise `SchemaValidationError` (Twingate is hub-and-spoke; only connector hosts
   "join" the network per §3 of the plan).
4. THE SYSTEM SHALL accept `advertise_routes` as `Optional[List[str]]` of CIDR
   strings; malformed CIDRs SHALL raise `SchemaValidationError`.
5. WHEN `exit_node` is `True` and `provider == "twingate"` THE SYSTEM SHALL raise
   `SchemaValidationError` (Twingate has no exit-node concept).

---

### Requirement 2: Hostname Template Rendering

**User Story:** As a provisioning author, I want a hostname template that renders
per-instance into stable MagicDNS-compatible names.

#### Acceptance Criteria

1. THE SYSTEM SHALL render the template against a context dict containing at minimum
   `{venue, group, index, name, region, zone}`.
2. THE SYSTEM SHALL replace `{var}` tokens; unknown tokens SHALL raise
   `SchemaSemanticError` with a list of the missing variable names.
3. WHEN the rendered string is not a valid DNS label per RFC 1123 (length 1–63,
   `[a-z0-9-]`, MUST NOT start or end with `-`, lowercase-only) THEN THE SYSTEM
   SHALL raise `SchemaSemanticError`.
4. WHEN two instances in the same instance group render to the same hostname THEN
   THE SYSTEM SHALL raise `SchemaSemanticError` listing the colliding names.
5. THE SYSTEM SHALL normalise rendered output by lowercasing and replacing any
   `_` with `-`; if normalisation would produce a label that still violates
   RFC 1123, the SemanticError is raised post-normalisation.

---

### Requirement 3: Renderer API

**User Story:** As a framework author, I want a single function that callers use to
render a template across a group.

#### Acceptance Criteria

1. THE SYSTEM SHALL expose `render_hostnames(*, template: str, contexts:
   List[Dict[str, Any]]) -> List[str]`.
2. THE SYSTEM SHALL return a list of rendered hostnames in the same order as
   `contexts`.
3. WHEN any single context fails validation THE SYSTEM SHALL raise the
   `SchemaSemanticError` for that context immediately; no partial results are
   returned.

---

### Requirement 4: Credential Resolution

**User Story:** As a framework author, I want the credential to resolve through the
existing `codecraftai-credentials` registry, never as a raw string.

#### Acceptance Criteria

1. THE SYSTEM SHALL accept `control_plane_credential` as the **name** of a
   credential registered in the credential vault, not as a raw token.
2. WHEN the named credential is not registered THE SYSTEM SHALL raise
   `SchemaSemanticError` during lifecycle `validate`.
3. WHEN the named credential's type is incompatible with the declared `provider`
   (e.g. `TwingateServiceAccountCredential` with `provider="tailscale"`) THE
   SYSTEM SHALL raise `SchemaSemanticError`.

---

### Requirement 5: Cloud-init Renderer Contract

**User Story:** As a venue-provisioner author, I want a stable contract for producing
the cloud-init `runcmd` / `write_files` payload from a `VPNJoinSpec`.

#### Acceptance Criteria

1. THE SYSTEM SHALL expose a `render_cloud_init(*, spec: VPNJoinSpec, authkey: str,
   rendered_hostname: str, image_family: str) -> Dict[str, Any]` function returning
   a cloud-init document fragment.
2. THE SYSTEM SHALL produce a fragment that — when merged with the rest of the
   user-data — is a valid cloud-init YAML document for every supported `VPNJoinSpec`
   permutation.
3. THE SYSTEM SHALL quote the auth key in every shell position it appears in to
   prevent shell-injection via tag values or auth keys containing whitespace or
   metacharacters.
4. WHERE the image does not ship `tailscale` THE SYSTEM SHALL prepend the official
   install snippet (`curl -fsSL https://tailscale.com/install.sh | sh`) only after
   verifying the family is supported.

---

### Requirement 6: Property Test Invariants

**User Story:** As a maintainer, I want hypothesis-based coverage of the renderer
because the input space is enormous.

#### Acceptance Criteria

1. THE SYSTEM SHALL include property tests asserting:
   - For any context where `{index}` ranges over `[0, N)` and the template includes
     `{index}`, all N rendered names are unique.
   - For any rendered name, it is a valid RFC 1123 DNS label.
   - For any spec, `render_cloud_init(...)` produces YAML that `yaml.safe_load`
     parses without error.
   - For any spec, the rendered cloud-init contains the auth key exactly once and
     always inside a quoted shell argument.
