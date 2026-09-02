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

- [ ] 12. Migrate the venue user-data renderers (20 call sites of
  `render_cloud_init`) to `render_instance_user_data` so every venue ships the
  Python fragment; until then only venues that adopt the composer honour
  `python_environments`
- [ ] 13. Credentialed private index: `index_credential` naming a vault entry,
  minted at render time into the `0400` pip.conf
- [ ] 14. Property tests (hypothesis) for YAML validity and quoting round-trips,
  matching `test_property_cloud_init.py`
- [ ] 15. Azure CSE / vSphere wrappers for the Python fragment (the VPN renderer
  has them; the composer currently produces cloud-init only)
- [ ] 16. Live verification on a stock image without `python3-venv` (needs a
  fresh cloud host or container)
