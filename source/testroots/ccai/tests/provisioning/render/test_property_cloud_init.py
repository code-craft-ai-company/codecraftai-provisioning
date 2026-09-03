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

from ccai.testbase.properties import given
from ccai.testbase.properties import strategies as st

import yaml

from ccai.interfaces.vpnjoinspec import VPNJoinSpec
from ccai.provisioning.cloudinit.vpncloudinitrenderer import (
    render_cloud_init, render_azure_cse,
)


_LINUX_FAMILIES = ("ubuntu", "debian", "rhel", "rocky", "almalinux", "fedora",
                   "amazon-linux")

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


# These are module-level functions on purpose.  The testbase sequencer
# collects module-level ``test_*`` and drives ``@given`` from the metadata the
# decorator records; a @given-decorated TestCase *method* is never given its
# generated arguments, so it cannot run.

_COMMON = dict(spec=_tailscale_spec_strategy(), authkey=_authkey_st,
               hostname=_hostname_st, family=st.sampled_from(_LINUX_FAMILIES))


@given(constraints={"max_examples": 30}, **_COMMON)
def test_render_round_trips_through_yaml(spec, authkey, hostname, family) -> None:
    """
        The rendered document survives a YAML dump and parse with its
        structural keys intact.
    """
    doc = render_cloud_init(spec=spec, authkey=authkey,
                            rendered_hostname=hostname,
                            image_family=family)

    parsed = yaml.safe_load(yaml.safe_dump(doc))

    assert "write_files" in parsed
    assert "runcmd" in parsed
    return


@given(constraints={"max_examples": 30}, **_COMMON)
def test_authkey_is_only_inside_write_files(spec, authkey, hostname,
                                            family) -> None:
    """
        The auth key appears only in the root-only key file -- never in the
        bring-up script and never in runcmd, where it would reach cloud-init's
        logs and the process table.
    """
    doc = render_cloud_init(spec=spec, authkey=authkey,
                            rendered_hostname=hostname,
                            image_family=family)

    authkey_file = doc["write_files"][0]
    assert authkey_file["path"] == "/etc/tailscale/authkey"
    assert authkey_file["content"] == authkey

    bringup_content = doc["write_files"][1]["content"]
    assert authkey not in bringup_content
    for entry in doc["runcmd"]:
        assert authkey not in json.dumps(entry)
    return


@given(constraints={"max_examples": 30}, **_COMMON)
def test_tailscale_up_authkey_uses_quoted_var(spec, authkey, hostname,
                                              family) -> None:
    """
        The bring-up script reaches the auth key through a quoted shell
        variable rather than interpolating it.
    """
    doc = render_cloud_init(spec=spec, authkey=authkey,
                            rendered_hostname=hostname,
                            image_family=family)

    bringup_content = doc["write_files"][1]["content"]

    matched = re.search(r'--auth-key=("\$\{AUTHKEY\}"|\'\$\{AUTHKEY\}\')',
                        bringup_content)
    assert matched is not None
    return


@given(constraints={"max_examples": 20}, **_COMMON)
def test_same_inputs_produce_byte_identical_output(spec, authkey, hostname,
                                                   family) -> None:
    """
        Rendering is deterministic, so an unchanged spec does not churn
        user-data and force a needless instance replacement.
    """
    first = yaml.safe_dump(render_cloud_init(
        spec=spec, authkey=authkey, rendered_hostname=hostname,
        image_family=family,
    ), sort_keys=True)
    second = yaml.safe_dump(render_cloud_init(
        spec=spec, authkey=authkey, rendered_hostname=hostname,
        image_family=family,
    ), sort_keys=True)

    assert first == second
    return


@given(constraints={"max_examples": 20}, **_COMMON)
def test_azure_cse_json_roundtrip(spec, authkey, hostname, family) -> None:
    """
        The Azure custom-script-extension payload survives a JSON round trip.
    """
    doc = render_azure_cse(spec=spec, authkey=authkey,
                           rendered_hostname=hostname,
                           image_family=family)

    parsed = json.loads(json.dumps(doc))

    assert "settings" in parsed
    return
