# Requirements — Python Environment Bootstrap

## Introduction

The `python-env-bootstrap` feature provides `codecraftai-provisioning` with a
first-boot path for deploying Python virtual environments with a declared
dependency set onto freshly provisioned Linux hosts.  It is the cloud-init
counterpart of the `python-environment-management` sysman contract
(`codecraftai-sysman-common/specs/contracts/python-environment-management/contract.md`):
the sysman manager converges an environment on a host the runner can already
reach; this feature produces the environment *before* any runner reaches the
host, so that the host is useful from its first boot.

The feature consists of:

- `PythonEnvironmentSpec` (in `codecraftai-foundations`,
  `ccai.interfaces.pythonenvspec`) — the declarative shape, attached to
  `CloudInstance.python_environments`.
- `render_python_env_cloud_init` — the venue-shared renderer producing a
  cloud-init fragment (prerequisite `packages`, root-only bootstrap scripts,
  `runcmd`).
- `merge_cloud_init_fragments` — the helper that combines the VPN and Python
  fragments.
- `render_instance_cloud_init` / `render_instance_user_data` — the composer
  venues call to obtain the complete document for an instance.

The bootstrap script's step order and `pip` argv shape intentionally match
`PythonEnvironmentManagementBase.deploy`, so a later sysman run against the same
host reports `SKIPPED` for every step.

---

## Requirements

### Requirement 1: Declarative Spec

**User Story:** As a spec author, I want to declare a Python environment on a
`CloudInstance` the same way I declare a VPN join.

#### Acceptance Criteria

1. THE SYSTEM SHALL expose `PythonEnvironmentSpec` from
   `ccai.interfaces.pythonenvspec` with fields `path` (required), `name`,
   `packages`, `requirements_files`, `constraints_files`, `interpreter`
   (default `python3`), `system_site_packages`, `upgrade_pip` (default True),
   `upgrade_packages`, `recreate`, `owner`, `index_url`, `extra_index_urls`,
   `trusted_hosts`, `pip_options`.
2. THE SYSTEM SHALL reject a relative or root `path`, any value containing a
   newline or NUL, a `name` outside `[A-Za-z0-9][A-Za-z0-9._-]{0,62}`, an
   `owner` outside `user[:group]`, an index URL that is not `http(s)://` or
   `file://` without whitespace, a trusted host that is not `host[:port]`, and
   `constraints_files` without `requirements_files`, raising
   `SchemaValidationError`.
3. THE SYSTEM SHALL derive `slug` from `name` or, when absent, from `path` with
   the leading slash removed and unsafe characters replaced by `-`.
4. `CloudInstance` SHALL accept `python_environments: list[PythonEnvironmentSpec]`,
   reject non-spec entries (`SchemaValidationError`) and duplicate paths
   (`SchemaSemanticError`), and promote dict payloads in `from_dict`.

---

### Requirement 2: Render the Cloud-Init Fragment

**User Story:** As a venue provisioner, I want one shared renderer that turns
the specs into a cloud-init fragment I can merge into `user_data`.

#### Acceptance Criteria

1. WHEN `render_python_env_cloud_init(specs, image_family)` is called THE
   SYSTEM SHALL return a dict with `package_update: True`, `packages` (the
   family's interpreter prerequisites), `write_files`, and `runcmd`.
2. THE SYSTEM SHALL emit, per spec and in spec order, a root-only `0700`
   bootstrap script at `/etc/ccai/python-env/<slug>.sh` and a `runcmd` entry
   invoking it.
3. WHEN a spec carries any index configuration THE SYSTEM SHALL emit a
   root-only `0400` `/etc/ccai/python-env/<slug>.pip.conf` before the script and
   reference it from the script through `PIP_CONFIG_FILE`; the URLs SHALL NOT
   appear in the script or in `runcmd`.
4. THE SYSTEM SHALL map image families to prerequisites: Ubuntu / Debian →
   `python3 python3-venv python3-pip`; RHEL / Rocky / AlmaLinux / Fedora /
   Amazon Linux → `python3 python3-pip`; accepting canonical tokens and the
   aliases `normalize_family` knows.
5. THE SYSTEM SHALL raise `CloudInitRendererError` for `windows-server` (with a
   hint naming `WindowsPythonEnvironmentManager`), for unknown families, for an
   empty spec list, for a non-spec entry, and for duplicate paths or slugs.
6. Rendering SHALL be deterministic: identical inputs produce byte-identical
   YAML.

---

### Requirement 3: Bootstrap Script Semantics

#### Acceptance Criteria

1. THE SCRIPT SHALL start with `#!/bin/bash` and `set -euo pipefail`.
2. THE SCRIPT SHALL create the environment with
   `"${PY}" -m venv [--system-site-packages] "${VENV}"` only when
   `${VENV}/bin/python` is not executable, after `rm -rf "${VENV}"` when
   `recreate` is set.
3. THE SCRIPT SHALL invoke pip as
   `"${VENV}/bin/python" -m pip --disable-pip-version-check --no-input …`.
4. THE SCRIPT SHALL run, in order and each only when applicable:
   `install --upgrade pip`; `install [--upgrade] [pip_options] -r … -c …`;
   `install [--upgrade] [pip_options] <packages…>`; `chown -R <owner> "${VENV}"`.
5. Every spec-supplied value placed on a shell line SHALL be single-quoted via
   `quote_for_shell`.

---

### Requirement 4: Credentialed Private Index

**User Story:** As a spec author, I want to install from a private index by
naming a vault credential, without any secret appearing in the spec, the
venue code, the runcmd, or the cloud-init log.

#### Acceptance Criteria

1. `resolve_index_credential(spec, credential_lookup)` SHALL resolve
   `spec.index_credential` through the caller-supplied lookup and map
   `BasicCredential` → (username, password), `PersonalApiTokenCredential` →
   (username, token), `ApiTokenCredential` / `SecretTokenCredential` →
   (`__token__`, token); any other class, `None`, or an ordinary lookup error
   SHALL raise `SchemaSemanticError`. A `ConfigurationError` raised by the
   lookup (a missing vault entry) SHALL propagate unchanged: it derives from
   `BaseException` by design so that a run started with wrong configuration
   terminates past any ordinary handler.
2. `collect_bootstrap_secrets(instances, credential_lookup)` SHALL resolve each
   distinct reference once into a `BootstrapSecrets`.
3. `ProvisioningEngine` SHALL accept `credential_lookup`; LOAD_VALIDATE SHALL
   resolve every named `index_credential` (raising `SchemaSemanticError` when
   one is named and no lookup is configured), and `apply` SHALL bind the
   resolved `BootstrapSecrets` (via `bind_bootstrap_secrets`) around every
   apply stage and clear it afterwards. Dry-run applies SHALL bind nothing.
4. `render_python_env_cloud_init` and the composer SHALL accept an optional
   `secrets` argument and otherwise read `current_bootstrap_secrets()`; a spec
   naming a credential that neither resolves SHALL raise
   `CloudInitRendererError` rather than render an unauthenticated URL.
5. The credential SHALL be embedded as percent-encoded URL userinfo into
   `index_url` and into `extra_index_urls` entries on the same host, only
   inside the `0400` pip configuration; it SHALL appear nowhere else in the
   rendered document.
6. `IndexCredential` and `BootstrapSecrets` SHALL never expose the secret
   through `repr`.

---

### Requirement 5: Merge and Compose

#### Acceptance Criteria

1. `merge_cloud_init_fragments(*fragments)` SHALL concatenate list-valued keys in
   argument order, skip `None`, tolerate equal scalars, raise
   `CloudInitRendererError` on conflicting scalars, and never mutate its inputs.
2. `render_instance_cloud_init(instance, authkey, rendered_hostname)` SHALL
   return `None` when the instance declares neither `vpn_join` nor
   `python_environments`; otherwise the merged fragment with VPN first, Python
   environments second, and a raw `user_data_script` appended as a final
   `["sh", "-c", script]` `runcmd` entry.
3. `render_instance_user_data` SHALL return the raw script verbatim when it is
   the only bootstrap content, `None` when there is none, and otherwise a
   `#cloud-config` document.
