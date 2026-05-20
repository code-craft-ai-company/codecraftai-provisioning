# Implementation Plan — Cloud-Init Injection

## Renderers

- [x] 1. Create `vpncloudinitrenderer.py` with `render_cloud_init`
- [x] 2. Implement Tailscale install + bring-up branch per Linux family
- [x] 3. Implement Twingate connector install branch
- [x] 4. Reject unsupported image families with `CloudInitRendererError`

## Quoting Helpers

- [x] 5. Create `secretquoting.py`
- [x] 6. Implement `quote_for_shell(value)` (double-quote with escape)
- [x] 7. Implement `write_authkey_file_block(authkey)` returning the write_files entry

## Azure CSE Wrapper

- [x] 8. Create `azurecserenderer.py`
- [x] 9. Implement PowerShell branch for Windows image families
- [x] 10. Implement bash branch for Linux image families
- [x] 11. Return `{settings, protectedSettings}` dict matching CSE schema

## vSphere Guest-Customization Wrapper

- [x] 12. Create `vsphereguestcustomizationrenderer.py`
- [x] 13. Linux: place cloud-init in `userData`
- [x] 14. Windows: place commands in sysprep `RunOnceCommands`

## Integration

- [x] 15. Document the call from venue provisioners at instance-create time
- [x] 16. Document the call from `BOOTSTRAP_VPN` stage for verify-only re-checks

## Tests — Examples

- [x] 17. `test_render_cloud_init_tailscale_ubuntu_snapshot`
- [x] 18. `test_render_cloud_init_twingate_ubuntu_snapshot`
- [x] 19. `test_render_handles_tags_with_whitespace_safely`
- [x] 20. `test_render_handles_authkey_with_shell_metachars`
- [x] 21. `test_render_rejects_unsupported_image_family`
- [x] 22. `test_render_azure_cse_windows_powershell`
- [x] 23. `test_render_vsphere_linux_userdata_present`

## Tests — Property (hypothesis) ⊙

- [x] 24. `test_property_cloud_init_yaml_validity_for_any_spec`
- [x] 25. `test_property_authkey_appears_exactly_once_and_quoted`
- [x] 26. `test_property_tag_roundtrip_through_yaml`
- [x] 27. `test_property_azure_cse_json_validity`

## Documentation

- [x] 28. Document the §8 single-renderer commitment in module docstring
- [x] 29. Cross-link `vpn-join-spec` and venue provisioner specs
