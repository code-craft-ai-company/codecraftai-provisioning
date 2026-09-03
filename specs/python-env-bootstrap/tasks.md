# Implementation Plan — Python Environment Bootstrap

Checked items (`[x]`) are implemented and covered by tests.

## Spec (codecraftai-foundations)

- [x] 1. Create `ccai.interfaces.pythonenvspec.PythonEnvironmentSpec`
- [x] 2. Validation rules (path, name, newline/NUL, owner, index URLs, trusted
  hosts, constraints-without-requirements)
- [x] 3. `slug` and `has_index_configuration` properties
- [x] 4. `test_pythonenvspec.py` in `source/tests/ccai_tests/interfaces/`

## Model (codecraftai-provisioning)

- [x] 5. `CloudInstance.python_environments` slot with entry-type and duplicate-path
  validation and `from_dict` promotion
- [x] 6. `test_cloudinstance_python_environments.py`

## Renderers

- [x] 7. `pythonenvcloudinitrenderer.py` — `render_python_env_cloud_init`,
  `render_bootstrap_script`, `render_pip_config`, path helpers, family table
- [x] 8. `cloudinitmerge.py` — `merge_cloud_init_fragments`
- [x] 9. `bootstraprenderer.py` — `render_instance_cloud_init`,
  `render_instance_user_data`
- [x] 10. `test_python_env_cloud_init_rendering.py` (script, pip.conf, fragment,
  merge, composer)

## Verification

- [x] 11. Live parity on Ubuntu 24.04 (2026-09-02): the rendered script executed
  under bash created the venv and installed the pins; a second run was a no-op;
  `UbuntuPythonEnvironmentManager.deploy` against the result reported every
  step `SKIPPED`.

## Follow-ups

- [x] 12. Migrate the venue user-data renderers to the shared composer so every
  venue ships the Python fragment (2026-09-02): crusoe, digitalocean,
  equinix_metal, hetzner, lambdalabs, nebius, vultr, xcpng, aws, google, oracle,
  azure (Linux custom_data) via `render_instance_user_data`; libvirt, nutanix,
  proxmox via `render_instance_cloud_init` + `merge_cloud_init_fragments`;
  linode via a new `render_instance` method used by the apply stage; vsphere
  (Linux userData) and hyperv `build_iso` (new `python_environments`
  parameter) merge `render_python_env_cloud_init` directly because they
  own venue-specific payload shapes.  Windows paths (azure CSE, hyperv
  SetupComplete, vsphere runOnceCommands) are unchanged.  Covered by
  `render/test_venue_python_env_wiring.py` (15 tests) and the full
  testbase venue suite (532/533 before and after).
- [x] 13. Credentialed private index (2026-09-02): `index_credential` on the
  spec; `bootstrapsecrets.py` (container + contextvar binding);
  `indexcredentialresolver.py`; engine `credential_lookup` with resolution at
  LOAD_VALIDATE and binding around apply; renderer / composer `secrets`
  parameter with ambient fallback and hard failure on an unresolved
  reference.  Tests: `render/test_index_credentials.py`,
  `engine/test_bootstrap_secrets_binding.py`, foundations spec tests.
- [ ] 14. Property tests (hypothesis) for YAML validity and quoting round-trips,
  matching `test_property_cloud_init.py`
- [x] 15. Linux payload shapes beyond plain user-data are covered by the venue
  migration (vSphere guest-customisation userData, Hyper-V NoCloud ISO,
  libvirt seed ISO, Proxmox snippet, Nutanix base64).  Windows shapes (Azure
  CSE PowerShell, vSphere runOnceCommands, Hyper-V SetupComplete) remain out
  of scope by design: cloudbase-init has no `write_files` + bash `runcmd`
  model, and the sysman `WindowsPythonEnvironmentManager` converges Windows
  hosts after boot.
- [ ] 16. Live verification on a stock image without `python3-venv` (needs a
  fresh cloud host or container)
