"""
    .. module:: test_property_cloud_init
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Property-based tests for the cloud-init VPN renderer.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import json
import re
import unittest

from hypothesis import given, settings, strategies as st

import yaml

from ccai.provisioning.model.vpn.vpnjoinspec import VPNJoinSpec
from ccai.provisioning.cloudinit.vpncloudinitrenderer import (
    render_cloud_init, render_azure_cse,
)


_LINUX_FAMILIES = ("ubuntu", "debian", "rhel", "fedora", "amazonlinux")

_tag_st = st.lists(
    st.text(alphabet=st.characters(blacklist_categories=("Cs",)),
            min_size=1, max_size=10),
    max_size=4,
)

_hostname_st = st.text(
    alphabet=st.characters(
        whitelist_categories=("Ll", "Nd"),
        whitelist_characters="-",
    ),
    min_size=1, max_size=20,
)

_authkey_st = st.text(
    alphabet=st.characters(blacklist_categories=("Cs", "Cc")),
    min_size=1, max_size=40,
).map(lambda s: "tskey-auth-" + s)


def _tailscale_spec_strategy() -> st.SearchStrategy:
    rtnval = st.builds(
        lambda tags, exit_node: VPNJoinSpec(
            provider="tailscale",
            control_plane_credential="ts-oauth",
            hostname_template="{name}",
            advertise_tags=tags,
            exit_node=exit_node,
        ),
        tags=_tag_st,
        exit_node=st.booleans(),
    )
    return rtnval


class CloudInitYamlValidityProperty(unittest.TestCase):

    @settings(max_examples=30, deadline=None)
    @given(spec=_tailscale_spec_strategy(),
           authkey=_authkey_st,
           hostname=_hostname_st,
           family=st.sampled_from(_LINUX_FAMILIES))
    def test_render_round_trips_through_yaml(self, spec, authkey,
                                             hostname, family) -> None:
        doc = render_cloud_init(spec=spec, authkey=authkey,
                                rendered_hostname=hostname,
                                image_family=family)
        text = yaml.safe_dump(doc)
        parsed = yaml.safe_load(text)
        self.assertIn("write_files", parsed)
        self.assertIn("runcmd", parsed)
        return


class AuthkeyAppearsOnceProperty(unittest.TestCase):

    @settings(max_examples=30, deadline=None)
    @given(spec=_tailscale_spec_strategy(),
           authkey=_authkey_st,
           hostname=_hostname_st,
           family=st.sampled_from(_LINUX_FAMILIES))
    def test_authkey_is_only_inside_write_files(self, spec, authkey,
                                                hostname, family) -> None:
        doc = render_cloud_init(spec=spec, authkey=authkey,
                                rendered_hostname=hostname,
                                image_family=family)
        # The authkey must appear exactly once and only in the write_files
        # entry for /etc/tailscale/authkey.
        authkey_file = doc["write_files"][0]
        self.assertEqual(authkey_file["path"], "/etc/tailscale/authkey")
        self.assertEqual(authkey_file["content"], authkey)

        bringup_content = doc["write_files"][1]["content"]
        self.assertNotIn(authkey, bringup_content)
        for entry in doc["runcmd"]:
            self.assertNotIn(authkey, json.dumps(entry))
        return


class AuthkeyQuotedInShellProperty(unittest.TestCase):

    @settings(max_examples=30, deadline=None)
    @given(spec=_tailscale_spec_strategy(),
           authkey=_authkey_st,
           hostname=_hostname_st,
           family=st.sampled_from(_LINUX_FAMILIES))
    def test_tailscale_up_authkey_uses_quoted_var(self, spec, authkey,
                                                  hostname, family) -> None:
        doc = render_cloud_init(spec=spec, authkey=authkey,
                                rendered_hostname=hostname,
                                image_family=family)
        bringup_content = doc["write_files"][1]["content"]
        # Confirm the auth-key is referenced via the quoted shell variable.
        matched = re.search(r'--auth-key=("\$\{AUTHKEY\}"|\'\$\{AUTHKEY\}\')',
                            bringup_content)
        self.assertIsNotNone(matched)
        return


class DeterminismProperty(unittest.TestCase):

    @settings(max_examples=20, deadline=None)
    @given(spec=_tailscale_spec_strategy(),
           authkey=_authkey_st,
           hostname=_hostname_st,
           family=st.sampled_from(_LINUX_FAMILIES))
    def test_same_inputs_produce_byte_identical_output(self, spec, authkey,
                                                       hostname,
                                                       family) -> None:
        first = yaml.safe_dump(render_cloud_init(
            spec=spec, authkey=authkey, rendered_hostname=hostname,
            image_family=family,
        ), sort_keys=True)
        second = yaml.safe_dump(render_cloud_init(
            spec=spec, authkey=authkey, rendered_hostname=hostname,
            image_family=family,
        ), sort_keys=True)
        self.assertEqual(first, second)
        return


class AzureCseJsonValidityProperty(unittest.TestCase):

    @settings(max_examples=20, deadline=None)
    @given(spec=_tailscale_spec_strategy(),
           authkey=_authkey_st,
           hostname=_hostname_st,
           family=st.sampled_from(_LINUX_FAMILIES))
    def test_azure_cse_json_roundtrip(self, spec, authkey, hostname,
                                      family) -> None:
        doc = render_azure_cse(spec=spec, authkey=authkey,
                               rendered_hostname=hostname,
                               image_family=family)
        text = json.dumps(doc)
        parsed = json.loads(text)
        self.assertIn("settings", parsed)
        return


if __name__ == "__main__":
    unittest.main()
