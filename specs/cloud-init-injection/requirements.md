# Requirements

## Introduction

Every venue provisioner needs to inject a bootstrap payload into newly created
instances: cloud-init `user_data` on Linux cloud VMs, the Azure Custom Script
Extension on Azure Windows VMs, vSphere guest-customization specs on vCenter VMs.
The contents of those payloads — install the Tailscale or Twingate daemon, bring up
the link with a freshly-minted auth key, configure the hostname, advertise routes —
are the **same** regardless of venue.

This spec owns the shared helpers that render those payloads.  Venue provisioners
call into this module instead of duplicating cloud-init authoring across nine venue
plugins.  The module owns three contracts:

1. The cloud-init YAML produced is valid for **every** permutation of `VPNJoinSpec`
   (property tested).
2. Auth keys and other secrets never appear unquoted in any shell position.
3. Venue-specific wrappers (Azure CSE, vSphere guest-customization) re-use the same
   underlying cloud-init document, with adaptors for the venue's payload format.

---

## Requirements

### Requirement 1: Cloud-Init Renderer

**User Story:** As a venue-provisioner author, I want one function that produces the
cloud-init document fragment for a `VPNJoinSpec`.

#### Acceptance Criteria

1. THE SYSTEM SHALL expose `render_cloud_init(*, spec: VPNJoinSpec, authkey: str,
   rendered_hostname: str, image_family: str) -> Dict[str, Any]` returning a
   cloud-init document fragment.
2. THE SYSTEM SHALL produce output that, when serialised with `yaml.safe_dump` and
   merged with any other user-data, is a valid cloud-init document.
3. WHERE `image_family` resolves (via `normalize_family`, so aliases such as
   `amazonlinux` are accepted) to a Linux `ImageFamily` member — `ubuntu`, `debian`,
   `rhel`, `rocky`, `almalinux`, `fedora`, `amazon-linux` — THE
   SYSTEM SHALL prepend the appropriate install snippet only when the daemon is
   not in the image's default package set.
4. WHEN `spec.provider == "tailscale"` THE SYSTEM SHALL emit a `runcmd` line
   invoking `tailscale up` with `--auth-key`, `--hostname`, `--advertise-tags`,
   and the optional `--advertise-routes` / `--advertise-exit-node` flags.
5. WHEN `spec.provider == "twingate"` THE SYSTEM SHALL emit Twingate connector
   install + service-start commands rather than `tailscale up`.

---

### Requirement 2: Secret Quoting

**User Story:** As a security-conscious user, I want the auth key never to leak
through shell-interpretation surprises.

#### Acceptance Criteria

1. THE SYSTEM SHALL write the auth key into a root-owned file
   (`/etc/tailscale/authkey` mode `0400`) via `write_files`.
2. THE SYSTEM SHALL read the key in `runcmd` via a `cat`/`read` shell command
   inside double quotes, never via direct YAML string interpolation.
3. THE SYSTEM SHALL also quote `hostname` and every `advertise_tag` to prevent
   shell injection via tag values containing whitespace or metacharacters.
4. WHEN the auth key contains characters that would alter shell parsing if unquoted
   THE SYSTEM SHALL still produce a payload where the key parses correctly inside
   its quoted position.

---

### Requirement 3: Azure CSE Wrapper

**User Story:** As an Azure venue author, I want a helper that wraps the cloud-init
document in a Custom Script Extension payload for Windows VMs.

#### Acceptance Criteria

1. THE SYSTEM SHALL expose `render_azure_cse(*, spec: VPNJoinSpec, authkey,
   rendered_hostname, image_family) -> Dict[str, Any]` returning the CSE
   `protectedSettings` and `settings` dict shape Azure expects.
2. THE SYSTEM SHALL embed the install + bring-up commands as PowerShell rather than
   bash for Windows image families.
3. WHEN the image family is Linux THE SYSTEM SHALL produce a CSE that runs cloud-init
   payload assembly under bash equivalent to the standard `runcmd`.

---

### Requirement 4: vSphere Guest-Customization Wrapper

**User Story:** As a vSphere venue author, I want the same render-once function to
produce the guest-customization spec payload.

#### Acceptance Criteria

1. THE SYSTEM SHALL expose `render_vsphere_guest_customization(*, spec, authkey,
   rendered_hostname, image_family) -> Dict[str, Any]` returning a
   `VmGuestCustomizationSpec`-compatible dict.
2. THE SYSTEM SHALL place the cloud-init document in the guest-customization
   `userData` field for Linux guests and use sysprep `RunOnceCommands` for Windows
   guests.

---

### Requirement 5: Property-Test Invariants ⊙

**User Story:** As a maintainer, I want hypothesis-based proof that the renderer
holds its invariants over the input space.

#### Acceptance Criteria

1. THE SYSTEM SHALL include property tests asserting:
   - For any `VPNJoinSpec` permutation, the rendered cloud-init parses with
     `yaml.safe_load` without error.
   - For any auth-key string drawn from the hypothesis `text()` strategy, the key
     appears exactly once in the rendered payload and only inside the
     `write_files.content` block or inside double-quoted shell positions.
   - For any tag-list drawn from arbitrary strings, the rendered tag argument is
     valid `cloud-init` YAML when round-tripped.
   - For any rendered Azure CSE, the document is valid JSON when serialised.
