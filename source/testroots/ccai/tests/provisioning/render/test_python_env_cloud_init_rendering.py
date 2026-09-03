"""
    .. module:: test_python_env_cloud_init_rendering
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Unit tests for the Python-environment cloud-init renderer, the
               fragment merge helper, and the instance bootstrap composer.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import shlex
import unittest

import yaml

from ccai.interfaces.pythonenvspec import PythonEnvironmentSpec
from ccai.interfaces.schemasemanticerror import SchemaSemanticError
from ccai.interfaces.vpnjoinspec import VPNJoinSpec

from ccai.provisioning.cloudinit.bootstraprenderer import (
    render_instance_cloud_init, render_instance_user_data,
)
from ccai.provisioning.cloudinit.cloudinitmerge import merge_cloud_init_fragments
from ccai.provisioning.cloudinit.cloudinitrenderererror import (
    CloudInitRendererError
)
from ccai.provisioning.cloudinit.pythonenvcloudinitrenderer import (
    BOOTSTRAP_DIRECTORY, PREREQUISITE_PACKAGES_BY_FAMILY,
    bootstrap_script_path, pip_config_path, render_bootstrap_script,
    render_pip_config, render_python_env_cloud_init,
)
from ccai.provisioning.model.cloud.cloudimage import CloudImage
from ccai.provisioning.model.cloud.cloudinstance import CloudInstance
from ccai.provisioning.model.cloud.imagefamily import ImageFamily


def _spec(**overrides) -> PythonEnvironmentSpec:
    kwargs = {"path": "/opt/venvs/app", "packages": ["requests==2.32.3", "rich>=13"]}
    kwargs.update(overrides)
    rtnval = PythonEnvironmentSpec(**kwargs)
    return rtnval


def _instance(**overrides) -> CloudInstance:
    kwargs = {
        "name": "agent-01", "profile_ref": "profile",
        "image": CloudImage(family="ubuntu", version="24.04", architecture="x86_64"),
        "size": "general.small", "subnet": "subnet",
    }
    kwargs.update(overrides)
    rtnval = CloudInstance(**kwargs)
    return rtnval


def _script_lines(spec: PythonEnvironmentSpec) -> list:
    rtnval = render_bootstrap_script(spec=spec).splitlines()
    return rtnval


class BootstrapScriptTests(unittest.TestCase):

    def test_script_header_and_variables(self) -> None:
        lines = _script_lines(_spec())
        self.assertEqual(lines[0], "#!/bin/bash")
        self.assertEqual(lines[1], "set -euo pipefail")
        self.assertEqual(lines[2], "VENV='/opt/venvs/app'")
        self.assertEqual(lines[3], "PY='python3'")
        return

    def test_create_is_guarded_by_interpreter_presence(self) -> None:
        lines = _script_lines(_spec())
        self.assertIn('if [ ! -x "${VENV}/bin/python" ]; then', lines)
        self.assertIn('  "${PY}" -m venv "${VENV}"', lines)
        self.assertIn("fi", lines)
        return

    def test_pip_invocation_matches_sysman_argv_shape(self) -> None:
        lines = _script_lines(_spec())
        self.assertIn(
            'PIP=("${VENV}/bin/python" -m pip --disable-pip-version-check --no-input)',
            lines,
        )
        return

    def test_step_order_mirrors_deploy(self) -> None:
        spec = _spec(recreate=True, requirements_files=["/srv/r.txt"],
                     constraints_files=["/srv/c.txt"], owner="agent")
        lines = _script_lines(spec)
        order = [
            lines.index('rm -rf "${VENV}"'),
            lines.index('if [ ! -x "${VENV}/bin/python" ]; then'),
            lines.index('"${PIP[@]}" install --upgrade pip'),
            lines.index('"${PIP[@]}" install -r \'/srv/r.txt\' -c \'/srv/c.txt\''),
            lines.index('"${PIP[@]}" install \'requests==2.32.3\' \'rich>=13\''),
            lines.index('chown -R \'agent\' "${VENV}"'),
        ]
        self.assertEqual(order, sorted(order))
        return

    def test_optional_steps_absent_by_default(self) -> None:
        text = render_bootstrap_script(spec=_spec(upgrade_pip=False))
        self.assertNotIn("rm -rf", text)
        self.assertNotIn("install --upgrade pip", text)
        self.assertNotIn(" -r ", text)
        self.assertNotIn("chown", text)
        self.assertNotIn("PIP_CONFIG_FILE", text)
        self.assertNotIn("--system-site-packages", text)
        return

    def test_system_site_packages_and_upgrade_flags(self) -> None:
        spec = _spec(system_site_packages=True, upgrade_packages=True,
                     pip_options=["--no-cache-dir"])
        lines = _script_lines(spec)
        self.assertIn('  "${PY}" -m venv --system-site-packages "${VENV}"', lines)
        self.assertIn(
            '"${PIP[@]}" install --upgrade \'--no-cache-dir\' \'requests==2.32.3\' \'rich>=13\'',
            lines,
        )
        return

    def test_index_configuration_exported_via_pip_config_file(self) -> None:
        spec = _spec(index_url="https://pypi.internal/simple")
        lines = _script_lines(spec)
        self.assertIn("export PIP_CONFIG_FILE='/etc/ccai/python-env/opt-venvs-app.pip.conf'", lines)
        self.assertNotIn("pypi.internal", render_bootstrap_script(spec=spec))
        return

    def test_shell_metacharacters_are_quoted(self) -> None:
        spec = PythonEnvironmentSpec(
            path="/opt/it's here", packages=["pkg; rm -rf /", "$(evil)"],
            interpreter="/usr/bin/python3 -X utf8", owner="agent",
        )
        text = render_bootstrap_script(spec=spec)
        # Every quoted token must survive a POSIX split unchanged.
        for line in text.splitlines():
            if line.startswith("VENV="):
                self.assertEqual(shlex.split(line[5:]), ["/opt/it's here"])
            if line.startswith("PY="):
                self.assertEqual(shlex.split(line[3:]), ["/usr/bin/python3 -X utf8"])
            if "install '" in line:
                tokens = shlex.split(line.split("install", 1)[1])
                self.assertEqual(tokens, ["pkg; rm -rf /", "$(evil)"])
        return


class PipConfigTests(unittest.TestCase):

    def test_empty_when_no_index_configuration(self) -> None:
        self.assertEqual(render_pip_config(spec=_spec()), "")
        return

    def test_renders_all_three_keys_with_continuations(self) -> None:
        spec = _spec(index_url="https://a/simple",
                     extra_index_urls=["https://b/simple", "https://c/simple"],
                     trusted_hosts=["b", "c"])
        text = render_pip_config(spec=spec)
        self.assertEqual(
            text,
            "[global]\n"
            "index-url = https://a/simple\n"
            "extra-index-url =\n    https://b/simple\n    https://c/simple\n"
            "trusted-host =\n    b\n    c\n",
        )
        return


class FragmentTests(unittest.TestCase):

    def test_fragment_shape_for_ubuntu(self) -> None:
        doc = render_python_env_cloud_init(specs=[_spec()], image_family="ubuntu")
        self.assertTrue(doc["package_update"])
        self.assertEqual(doc["packages"], ["python3", "python3-venv", "python3-pip"])
        self.assertEqual([w["path"] for w in doc["write_files"]],
                         ["/etc/ccai/python-env/opt-venvs-app.sh"])
        self.assertEqual(doc["write_files"][0]["permissions"], "0700")
        self.assertEqual(doc["write_files"][0]["owner"], "root:root")
        self.assertEqual(doc["runcmd"], [["/etc/ccai/python-env/opt-venvs-app.sh"]])
        return

    def test_fragment_is_valid_yaml(self) -> None:
        doc = render_python_env_cloud_init(specs=[_spec()], image_family="ubuntu")
        parsed = yaml.safe_load(yaml.safe_dump(doc))
        self.assertEqual(parsed["runcmd"], doc["runcmd"])
        return

    def test_pip_conf_written_root_only_before_script(self) -> None:
        spec = _spec(index_url="https://pypi.internal/simple")
        doc = render_python_env_cloud_init(specs=[spec], image_family="ubuntu")
        paths = [w["path"] for w in doc["write_files"]]
        self.assertEqual(paths, [pip_config_path(spec=spec), bootstrap_script_path(spec=spec)])
        self.assertEqual(doc["write_files"][0]["permissions"], "0400")
        self.assertIn("index-url = https://pypi.internal/simple", doc["write_files"][0]["content"])
        return

    def test_prerequisites_per_family(self) -> None:
        for family, expected in PREREQUISITE_PACKAGES_BY_FAMILY.items():
            doc = render_python_env_cloud_init(specs=[_spec()], image_family=family.value)
            self.assertEqual(doc["packages"], expected, family)
        return

    def test_family_alias_is_normalised(self) -> None:
        doc = render_python_env_cloud_init(specs=[_spec()], image_family="rockylinux")
        self.assertEqual(doc["packages"], PREREQUISITE_PACKAGES_BY_FAMILY[ImageFamily.ROCKY])
        return

    def test_windows_family_rejected_with_hint(self) -> None:
        with self.assertRaises(CloudInitRendererError) as caught:
            render_python_env_cloud_init(specs=[_spec()], image_family="windows-server")
        self.assertIn("WindowsPythonEnvironmentManager", str(caught.exception))
        return

    def test_unknown_family_propagates_semantic_error(self) -> None:
        # Misuse of the model is a SchemaSemanticError and must not be
        # downgraded into a catchable renderer error.
        with self.assertRaises(SchemaSemanticError):
            render_python_env_cloud_init(specs=[_spec()], image_family="plan9")
        return

    def test_empty_specs_rejected(self) -> None:
        with self.assertRaises(CloudInitRendererError):
            render_python_env_cloud_init(specs=[], image_family="ubuntu")
        return

    def test_duplicate_path_rejected(self) -> None:
        with self.assertRaises(CloudInitRendererError):
            render_python_env_cloud_init(specs=[_spec(), _spec(name="other")], image_family="ubuntu")
        return

    def test_duplicate_slug_rejected(self) -> None:
        with self.assertRaises(CloudInitRendererError):
            render_python_env_cloud_init(
                specs=[_spec(path="/a", name="x"), _spec(path="/b", name="x")],
                image_family="ubuntu",
            )
        return

    def test_multiple_environments_keep_order(self) -> None:
        doc = render_python_env_cloud_init(
            specs=[_spec(path="/opt/a", name="a"), _spec(path="/opt/b", name="b")],
            image_family="debian",
        )
        self.assertEqual(doc["runcmd"], [[BOOTSTRAP_DIRECTORY + "/a.sh"], [BOOTSTRAP_DIRECTORY + "/b.sh"]])
        return

    def test_same_inputs_produce_byte_identical_output(self) -> None:
        first = yaml.safe_dump(render_python_env_cloud_init(specs=[_spec()], image_family="ubuntu"))
        second = yaml.safe_dump(render_python_env_cloud_init(specs=[_spec()], image_family="ubuntu"))
        self.assertEqual(first, second)
        return


class MergeTests(unittest.TestCase):

    def test_lists_concatenate_in_order_and_inputs_untouched(self) -> None:
        first = {"runcmd": [["a"]], "packages": ["p1"]}
        second = {"runcmd": [["b"]], "write_files": [{"path": "/x"}]}
        merged = merge_cloud_init_fragments(first, None, second)
        self.assertEqual(merged["runcmd"], [["a"], ["b"]])
        self.assertEqual(merged["packages"], ["p1"])
        self.assertEqual(merged["write_files"], [{"path": "/x"}])
        self.assertEqual(first, {"runcmd": [["a"]], "packages": ["p1"]})
        return

    def test_equal_scalars_tolerated(self) -> None:
        merged = merge_cloud_init_fragments({"package_update": True}, {"package_update": True})
        self.assertTrue(merged["package_update"])
        return

    def test_conflicting_scalars_raise(self) -> None:
        with self.assertRaises(CloudInitRendererError):
            merge_cloud_init_fragments({"package_update": True}, {"package_update": False})
        return

    def test_no_fragments_gives_empty_dict(self) -> None:
        self.assertEqual(merge_cloud_init_fragments(), {})
        return


class InstanceBootstrapTests(unittest.TestCase):

    def test_none_when_instance_declares_nothing(self) -> None:
        self.assertIsNone(render_instance_cloud_init(instance=_instance()))
        self.assertIsNone(render_instance_user_data(instance=_instance()))
        return

    def test_raw_script_only_passes_through_verbatim(self) -> None:
        inst = _instance(user_data_script="#!/bin/sh\necho hi")
        self.assertIsNone(render_instance_cloud_init(instance=inst))
        self.assertEqual(render_instance_user_data(instance=inst), "#!/bin/sh\necho hi")
        return

    def test_python_environments_only(self) -> None:
        inst = _instance(python_environments=[_spec()])
        doc = render_instance_cloud_init(instance=inst)
        self.assertEqual(doc["packages"], ["python3", "python3-venv", "python3-pip"])
        self.assertEqual(doc["runcmd"], [["/etc/ccai/python-env/opt-venvs-app.sh"]])
        return

    def test_vpn_then_python_then_raw_script_ordering(self) -> None:
        vpn = VPNJoinSpec(provider="tailscale", control_plane_credential="ts",
                          hostname_template="{name}", advertise_tags=["tag:lab"])
        inst = _instance(vpn_join=vpn, python_environments=[_spec()],
                         user_data_script="echo done")
        doc = render_instance_cloud_init(instance=inst, authkey="tskey-x")
        runcmd = doc["runcmd"]
        self.assertEqual(runcmd[-1], ["sh", "-c", "echo done"])
        self.assertEqual(runcmd[-2], ["/etc/ccai/python-env/opt-venvs-app.sh"])
        self.assertEqual(runcmd[1], ["/etc/tailscale/bringup.sh"])
        paths = [w["path"] for w in doc["write_files"]]
        self.assertLess(paths.index("/etc/tailscale/authkey"),
                        paths.index("/etc/ccai/python-env/opt-venvs-app.sh"))
        return

    def test_user_data_document_has_header_and_parses(self) -> None:
        inst = _instance(python_environments=[_spec()])
        text = render_instance_user_data(instance=inst)
        self.assertTrue(text.startswith("#cloud-config\n"))
        parsed = yaml.safe_load(text)
        self.assertIn("write_files", parsed)
        self.assertIn("packages", parsed)
        return

    def test_hostname_defaults_to_instance_name(self) -> None:
        vpn = VPNJoinSpec(provider="tailscale", control_plane_credential="ts",
                          hostname_template="{name}")
        inst = _instance(vpn_join=vpn)
        doc = render_instance_cloud_init(instance=inst, authkey="k")
        bringup = [w for w in doc["write_files"] if w["path"] == "/etc/tailscale/bringup.sh"][0]
        self.assertIn("HOST='agent-01'", bringup["content"])
        return


if __name__ == "__main__":
    unittest.main()
