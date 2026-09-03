"""
    .. module:: test_cloud_init_rendering
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Unit tests for the cloud-init VPN renderer.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import json
import re
import unittest

import yaml

from ccai.interfaces.vpnjoinspec import VPNJoinSpec
from ccai.provisioning.cloudinit.cloudinitrenderererror import (
    CloudInitRendererError
)
from ccai.provisioning.cloudinit.vpncloudinitrenderer import (
    render_cloud_init, render_azure_cse,
    render_vsphere_guest_customization,
)


def _tailscale_spec() -> VPNJoinSpec:
    rtnval = VPNJoinSpec(provider="tailscale",
                         control_plane_credential="ts-oauth",
                         hostname_template="{name}",
                         advertise_tags=["tag:lab", "tag:web"])
    return rtnval


def _twingate_spec() -> VPNJoinSpec:
    rtnval = VPNJoinSpec(provider="twingate",
                         control_plane_credential="tg-token",
                         hostname_template="{name}",
                         connector_only=True)
    return rtnval


class CloudInitTailscaleTests(unittest.TestCase):

    def test_render_produces_valid_yaml(self) -> None:
        doc = render_cloud_init(spec=_tailscale_spec(),
                                authkey="tskey-auth-abc",
                                rendered_hostname="web-01",
                                image_family="ubuntu")
        text = yaml.safe_dump(doc)
        parsed = yaml.safe_load(text)
        self.assertIn("write_files", parsed)
        self.assertIn("runcmd", parsed)
        return

    def test_authkey_lives_in_root_file_only(self) -> None:
        doc = render_cloud_init(spec=_tailscale_spec(),
                                authkey="tskey-auth-secret-xyz",
                                rendered_hostname="web-01",
                                image_family="ubuntu")
        text = yaml.safe_dump(doc)
        # The auth key appears exactly once — in the write_files content.
        occurrences = text.count("tskey-auth-secret-xyz")
        self.assertEqual(occurrences, 1)
        return

    def test_tailscale_up_authkey_uses_quoted_var(self) -> None:
        doc = render_cloud_init(spec=_tailscale_spec(),
                                authkey="tskey-auth-abc",
                                rendered_hostname="web-01",
                                image_family="ubuntu")
        bringup = doc["write_files"][1]["content"]
        # The auth-key argument must reference the shell variable, not the
        # literal key — and the variable expansion must be inside quotes.
        self.assertIn("--auth-key=\"${AUTHKEY}\"", bringup)
        return


class CloudInitTwingateTests(unittest.TestCase):

    def test_twingate_renders_connector_install(self) -> None:
        doc = render_cloud_init(spec=_twingate_spec(),
                                authkey="tg-token-abc",
                                rendered_hostname="connector-01",
                                image_family="ubuntu")
        runcmd = doc["runcmd"]
        joined = json.dumps(runcmd)
        self.assertIn("twingate", joined)
        return


class CloudInitImageFamilyTests(unittest.TestCase):

    def test_every_canonical_linux_family_renders(self) -> None:
        # CloudImage stores canonical ImageFamily tokens; every Linux member
        # must be accepted (amazon-linux, rocky and almalinux were rejected
        # before the renderer resolved families through normalize_family).
        for family in ("ubuntu", "debian", "rhel", "rocky", "almalinux",
                       "fedora", "amazon-linux"):
            with self.subTest(family=family):
                doc = render_cloud_init(spec=_tailscale_spec(),
                                        authkey="tskey-auth-abc",
                                        rendered_hostname="web-01",
                                        image_family=family)
                self.assertIn("runcmd", doc)
        return

    def test_family_aliases_are_accepted(self) -> None:
        for alias in ("amazonlinux", "amzn", "rockylinux", "redhat", "alma"):
            with self.subTest(alias=alias):
                doc = render_cloud_init(spec=_tailscale_spec(),
                                        authkey="tskey-auth-abc",
                                        rendered_hostname="web-01",
                                        image_family=alias)
                self.assertIn("runcmd", doc)
        return

    def test_windows_aliases_select_the_windows_branches(self) -> None:
        for alias in ("windows-server", "windows", "windows_server"):
            with self.subTest(alias=alias):
                cse = render_azure_cse(spec=_tailscale_spec(),
                                       authkey="tskey-auth-abc",
                                       rendered_hostname="web-01",
                                       image_family=alias)
                self.assertIn("powershell", cse["protectedSettings"]["commandToExecute"])
                guest = render_vsphere_guest_customization(
                    spec=_tailscale_spec(), authkey="tskey-auth-abc",
                    rendered_hostname="web-01", image_family=alias)
                self.assertIn("runOnceCommands", guest)
        return

    def test_unsupported_family_raises(self) -> None:
        with self.assertRaises(CloudInitRendererError):
            render_cloud_init(spec=_tailscale_spec(), authkey="x",
                              rendered_hostname="h", image_family="plan9")
        return


class CloudInitTagInjectionTests(unittest.TestCase):

    def test_tag_with_shell_metachars_is_quoted(self) -> None:
        spec = VPNJoinSpec(
            provider="tailscale",
            control_plane_credential="ts-oauth",
            hostname_template="{name}",
            advertise_tags=["tag:dangerous;rm -rf /"],
        )
        doc = render_cloud_init(spec=spec, authkey="tskey",
                                rendered_hostname="web-01",
                                image_family="ubuntu")
        bringup = doc["write_files"][1]["content"]
        # The dangerous payload must be inside the TAGS single-quoted scalar
        # — never reaching the shell's interpretation pass.
        self.assertIn("TAGS='tag:dangerous;rm -rf /'", bringup)
        return


class AzureCSETests(unittest.TestCase):

    def test_linux_azure_cse_json_serialises(self) -> None:
        doc = render_azure_cse(spec=_tailscale_spec(), authkey="tskey",
                               rendered_hostname="web-01",
                               image_family="ubuntu")
        # The dict must JSON-round-trip.
        text = json.dumps(doc)
        parsed = json.loads(text)
        self.assertIn("settings", parsed)
        # C6: the secret-bearing commandToExecute lives in protectedSettings,
        # never in the public settings block.
        self.assertNotIn("commandToExecute", parsed["settings"])
        self.assertIn("commandToExecute", parsed["protectedSettings"])
        return

    def test_linux_azure_cse_authkey_not_in_public_settings(self) -> None:
        """
            C6 regression: the auth-key file content must not appear in the
            public ``settings`` block of the Azure CSE payload.
        """
        doc = render_azure_cse(spec=_tailscale_spec(),
                               authkey="tskey-SECRET-LINUX",
                               rendered_hostname="web-01",
                               image_family="ubuntu")
        public_text = json.dumps(doc["settings"])
        self.assertNotIn("tskey-SECRET-LINUX", public_text)
        protected_text = json.dumps(doc["protectedSettings"])
        self.assertIn("tskey-SECRET-LINUX", protected_text)
        return

    def test_windows_azure_cse_authkey_not_in_public_settings(self) -> None:
        """
            C6 regression: the Windows CSE auth key must not appear in the
            public ``settings`` block.
        """
        doc = render_azure_cse(spec=_tailscale_spec(),
                               authkey="tskey-SECRET-WIN",
                               rendered_hostname="web-01",
                               image_family="windows-server")
        public_text = json.dumps(doc["settings"])
        self.assertNotIn("tskey-SECRET-WIN", public_text)
        self.assertNotIn("commandToExecute", doc["settings"])
        protected_text = json.dumps(doc["protectedSettings"])
        self.assertIn("tskey-SECRET-WIN", protected_text)
        return


class VSphereGuestCustomizationTests(unittest.TestCase):

    def test_linux_userdata_present(self) -> None:
        doc = render_vsphere_guest_customization(spec=_tailscale_spec(),
                                                 authkey="tskey",
                                                 rendered_hostname="web-01",
                                                 image_family="ubuntu")
        self.assertIn("userData", doc)
        self.assertIn("write_files", doc["userData"])
        return


class DeterminismTests(unittest.TestCase):

    def test_same_inputs_produce_byte_identical_output(self) -> None:
        spec = _tailscale_spec()
        first = yaml.safe_dump(render_cloud_init(
            spec=spec, authkey="tskey-determ",
            rendered_hostname="web-01", image_family="ubuntu",
        ), sort_keys=True)
        second = yaml.safe_dump(render_cloud_init(
            spec=spec, authkey="tskey-determ",
            rendered_hostname="web-01", image_family="ubuntu",
        ), sort_keys=True)
        self.assertEqual(first, second)
        return


if __name__ == "__main__":
    unittest.main()
