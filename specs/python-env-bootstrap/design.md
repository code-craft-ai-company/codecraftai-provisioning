# Design — Python Environment Bootstrap

## Overview

Provisioned hosts are only useful once their runtime is in place.  For the
Python-based agents and test runners this suite deploys, "runtime" means a
virtual environment with a pinned dependency set.  The sysman
`python-environment-management` feature converges such an environment through
an `ICommandRunner`, but a runner cannot reach a host until the host has booted,
joined the overlay, and accepted a session.  This feature closes that gap: it
renders the same environment declaration into cloud-init, so the environment
exists by the time the first runner connects — and the sysman manager, when it
does connect, finds nothing to do.

The design reuses three existing seams rather than inventing new ones:

| Concern | Reused |
|---|---|
| Declarative shape attached to an instance | `SchemaObject` / `Field`, placed beside `VPNJoinSpec` in `ccai.interfaces` |
| Shell-safe quoting | `secretquoting.quote_for_shell` |
| Fragment shape, error type, family handling | `vpncloudinitrenderer` conventions, `CloudInitRendererError`, `imagefamily.normalize_family` |
| Step order and pip argv | `PythonEnvironmentManagementBase.deploy` in `codecraftai-sysman-common` |

---

## Architecture

```
   CloudInstance.python_environments: [PythonEnvironmentSpec, ...]
                            │
                            ▼
   render_python_env_cloud_init(specs, image_family)
        │  packages: [python3, python3-venv, python3-pip]      (per family)
        │  write_files: <slug>.pip.conf (0400)?  <slug>.sh (0700)   per spec
        │  runcmd: [/etc/ccai/python-env/<slug>.sh]                 per spec
        ▼
   merge_cloud_init_fragments(vpn_fragment, python_fragment)
        ▲
        │  render_instance_cloud_init(instance, authkey, rendered_hostname)
        │  render_instance_user_data(...)  ──►  "#cloud-config\n..." | raw script | None
        │
   venue renderers (ship the document: base64 / verbatim / seed ISO / CSE)
```

`bootstraprenderer` is the single place that knows which instance slots yield
cloud-init fragments and in what order.  Every Linux venue path routes through
it; the two venues that own a richer payload shape (vsphere guest
customisation, Hyper-V NoCloud ISO) merge the Python fragment directly and are
listed in `tasks.md`.

---

## Rendered Fragment

```yaml
package_update: true
packages: [python3, python3-venv, python3-pip]
write_files:
  - path: /etc/ccai/python-env/opt-venvs-agent.pip.conf   # only with index config
    owner: root:root
    permissions: '0400'
    content: |
      [global]
      index-url = https://pypi.internal/simple
      trusted-host =
          pypi.internal
  - path: /etc/ccai/python-env/opt-venvs-agent.sh
    owner: root:root
    permissions: '0700'
    content: |
      #!/bin/bash
      set -euo pipefail
      VENV='/opt/venvs/agent'
      PY='python3'
      if [ ! -x "${VENV}/bin/python" ]; then
        "${PY}" -m venv "${VENV}"
      fi
      PIP=("${VENV}/bin/python" -m pip --disable-pip-version-check --no-input)
      export PIP_CONFIG_FILE='/etc/ccai/python-env/opt-venvs-agent.pip.conf'
      "${PIP[@]}" install --upgrade pip
      "${PIP[@]}" install -r '/opt/agent/requirements.txt'
      "${PIP[@]}" install 'requests==2.32.3' 'rich>=13'
      chown -R 'agent' "${VENV}"
runcmd:
  - [/etc/ccai/python-env/opt-venvs-agent.sh]
```

cloud-init runs the `packages` module before `runcmd`, so the interpreter
prerequisites are present when the script starts; `package_update: true` makes
that work on images whose package index is stale at first boot.

---

## Why the Script Mirrors the Manager

The script guards creation on `${VENV}/bin/python` being executable, uses
`python -m pip` with `--disable-pip-version-check --no-input`, and runs the
steps in the order remove → create → upgrade pip → requirements → packages.
That is exactly `PythonEnvironmentManagementBase.deploy` (see the sysman base
design).  The consequence is operational: a coordinator can attach the same
`PythonEnvironmentSpec` to the sysman manager after boot and get a `SKIPPED`
convergence, and can re-run the manager with a changed pin to update the
environment without caring which path built it.

The script deliberately does *not* reproduce the manager's PEP 508 satisfied
probe.  On first boot the environment is new, so pip's own resolver is the
cheaper and more correct idempotency check.

---

## Secret Handling

`PythonEnvironmentSpec` refuses credentials by construction: the URL fields
reject embedded userinfo, and no field accepts a token.  A private index is
declared by naming a vault entry in `index_credential`, and the secret flows
through one seam:

```
   spec.index_credential ("pypi:internal")
            │  LOAD_VALIDATE: ProvisioningEngine._resolve_bootstrap_secrets
            │  → collect_bootstrap_secrets(instances, credential_lookup)
            │  → resolve_index_credential: BasicCredential / token classes
            ▼
   BootstrapSecrets{index_credentials: {"pypi:internal": IndexCredential}}
            │  apply(): with bind_bootstrap_secrets(secrets): <all stages>
            ▼
   contextvar  ──►  render_python_env_cloud_init(..., secrets=None)
                    → current_bootstrap_secrets().credential_for(spec)
                    → render_pip_config(spec, credential)
                    → "index-url = https://svc:s3cret@host/simple"   (0400 file only)
```

The engine resolves once, so no venue provisioner touches the vault and no
venue signature changed; the renderer reads the ambient container unless a
caller passes one explicitly (tests, or a future coordinator).  The
`ContextVar` binding is per-thread and per-task, so concurrent engines in one
process cannot see each other's secrets.  A spec that names a credential the
run did not resolve is a hard `CloudInitRendererError` — the renderer never
downgrades to an unauthenticated URL.  Credentials are embedded only on
`index_url` and on `extra_index_urls` entries sharing its host, as
percent-encoded userinfo inside the `0400` pip configuration; `repr` of the
secret types is redacted so no log line or exception can carry a token.

---

## Windows

`windows-server` is rejected with a hint.  cloudbase-init does not share the
`write_files` + bash `runcmd` model, and the sysman
`WindowsPythonEnvironmentManager` already covers Windows once a WinRM or SSH
runner can reach the host.  An Azure CSE / PowerShell branch is a possible
extension if a Windows first-boot requirement materialises.

---

## Module Layout

```
codecraftai-foundations/source/packages/ccai/interfaces/
└── pythonenvspec.py                       # PythonEnvironmentSpec

codecraftai-provisioning/source/packages/ccai/provisioning/
├── cloudinit/
│   ├── pythonenvcloudinitrenderer.py      # render_python_env_cloud_init, script + pip.conf renderers
│   ├── cloudinitmerge.py                  # merge_cloud_init_fragments
│   ├── bootstraprenderer.py               # render_instance_cloud_init / render_instance_user_data
│   └── bootstrapsecrets.py                # IndexCredential, BootstrapSecrets, bind/current
├── model/pythonenv/indexcredentialresolver.py   # resolve_index_credential, collect_bootstrap_secrets
├── provisioningengine.py                  # credential_lookup, _resolve_bootstrap_secrets, apply binding
└── model/cloud/cloudinstance.py           # + python_environments slot

codecraftai-foundations/source/tests/ccai_tests/interfaces/test_pythonenvspec.py
codecraftai-provisioning/source/testroots/ccai/tests/provisioning/
├── render/test_python_env_cloud_init_rendering.py
└── model/cloud/test_cloudinstance_python_environments.py
```

---

## Correctness Properties

1. **Spec validation.** Every rejection rule in Requirement 1 raises
   `SchemaValidationError`; valid specs round-trip through `to_dict` /
   `from_dict`.
2. **Slug derivation.** `name` wins; otherwise the path-derived slug contains
   only `[A-Za-z0-9._-]`.
3. **Fragment shape.** `package_update`, `packages`, `write_files`, `runcmd`
   present; script `0700`, pip.conf `0400`, both `root:root`.
4. **Prerequisites per family.** Each supported family maps to the documented
   list; aliases normalise; Windows and unknown families raise.
5. **Script structure.** Header, guarded create, pip array, optional steps
   present only when configured, step order as specified.
6. **Quoting.** Paths, interpreter, packages, files, options, and owner
   survive `shlex.split` unchanged.
7. **Index isolation.** Index URLs appear only inside the pip.conf content.
8. **Merge.** Lists concatenate in order; equal scalars tolerate; conflicts
   raise; inputs untouched.
9. **Composition.** VPN before Python before raw script; `None` when nothing is
   declared; raw script verbatim when alone.
10. **Determinism.** Byte-identical output for identical inputs.
11. **Live parity.** The rendered script, executed with bash, produces an
    environment the sysman manager reports as fully `SKIPPED`.

---

## Testing Strategy

`unittest` classes under `source/testroots/ccai/tests/provisioning/render/`
and `model/cloud/`, with the spec's own tests in `codecraftai-foundations`.
Script structure is asserted line-by-line; quoting is asserted by feeding each
quoted token through `shlex.split`.  Property-based tests (hypothesis) for
YAML validity and quoting round-trips mirror the VPN renderer's and are listed
as a follow-up until the property harness is available in the environment.
Live parity (property 11) was exercised manually on Ubuntu 24.04 and is recorded
in `tasks.md`.
