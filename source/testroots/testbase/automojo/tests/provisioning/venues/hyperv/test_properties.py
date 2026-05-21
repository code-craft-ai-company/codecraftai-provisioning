"""
    .. module:: test_properties
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Property-based tests for the Hyper-V venue provisioner:
        idempotent apply, inverse destroy and notes-JSON round-trip.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Dict, List

from hypothesis import given, settings
from hypothesis import strategies as st

from automojo.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from automojo.provisioning.model.cloud.cloudvenue import CloudVenue
from automojo.provisioning.venues.hyperv.hvhostconfig import HvHostConfig
from automojo.provisioning.venues.hyperv.hvnotestranslator import (
    HvNotesTranslator
)
from automojo.provisioning.venues.hyperv.hypervcloudprovisioner import (
    HypervCloudProvisioner
)

from automojo.tests.provisioning.venues.hyperv import _specfactory
from automojo.tests.provisioning.venues.hyperv._mockclient import (
    MockHypervClient
)


def _build(*, with_vpn: bool, with_volume: bool):
    """
        Build a venue, mock client and provisioner for a property test.

        :param with_vpn: Whether the instance carries a VPNJoinSpec.
        :param with_volume: Whether a data volume is included.

        :returns: A (provisioner, client) tuple.
    """
    venue = CloudVenue(name="hyperv-prop", provider="hyperv",
                       endpoint="winrm://hv:5985",
                       region="lab", credential="hv-cred")
    host_config = HvHostConfig(host="hv-host")
    client = MockHypervClient()
    spec = _specfactory.make_basic_spec(with_vpn=with_vpn,
                                        with_volume=with_volume)
    provisioner = HypervCloudProvisioner(venue=venue, client=client,
                                         host_config=host_config, spec=spec)
    rtnval = (provisioner, client)
    return rtnval


@settings(max_examples=25, deadline=None)
@given(with_vpn=st.booleans(), with_volume=st.booleans())
def test_apply_idempotent(with_vpn, with_volume):
    """
        apply ∘ apply makes no further mutating calls on the second run.
    """
    provisioner, client = _build(with_vpn=with_vpn, with_volume=with_volume)
    aspects = ProvisioningAspects(runid="hvrun01", verify_timeout=10.0,
                                  verify_interval=0.01)

    provisioner.apply(aspects=aspects)
    mutations_after_first = client.mutation_total()

    second = provisioner.apply(aspects=aspects)
    mutations_after_second = client.mutation_total()

    assert mutations_after_second == mutations_after_first
    assert len(second.created) == 0
    return


@settings(max_examples=25, deadline=None)
@given(with_vpn=st.booleans(), with_volume=st.booleans())
def test_destroy_is_inverse_of_apply(with_vpn, with_volume):
    """
        destroy ∘ apply restores an empty host (modulo external state).
    """
    provisioner, client = _build(with_vpn=with_vpn, with_volume=with_volume)
    aspects = ProvisioningAspects(runid="hvrun01", verify_timeout=10.0,
                                  verify_interval=0.01)
    confirm = ProvisioningAspects(runid="hvrun01", confirm=True,
                                  verify_timeout=10.0, verify_interval=0.01)

    provisioner.apply(aspects=aspects)
    provisioner.destroy(aspects=confirm)

    assert len(client.vms_state) == 0
    assert len(client.switches_state) == 0
    assert len(client.vhdx_state) == 0
    return


_TAG_KEYS = st.text(alphabet="abcdefghijklmnop", min_size=1, max_size=8)
_TAG_VALUES = st.text(alphabet="abcdefghijklmnop0123", min_size=0,
                      max_size=12)


@settings(max_examples=60, deadline=None)
@given(tags=st.dictionaries(keys=_TAG_KEYS, values=_TAG_VALUES,
                            min_size=0, max_size=6),
       run_id=st.text(alphabet="abcdef0123-", min_size=1, max_size=20))
def test_notes_json_tag_round_trip_identity(tags, run_id):
    """
        decode(encode(tags, run_id)) recovers the tags and run-id exactly.
    """
    translator = HvNotesTranslator()

    encoded = translator.encode(neutral_tags=tags, run_id=run_id)
    envelope = translator.decode(notes_str=encoded)

    assert envelope.run_id == run_id
    assert envelope.tags == tags
    assert translator.owned_by(notes_str=encoded, run_id=run_id) is True
    return


def test_notes_decode_tolerates_garbage():
    """
        decode of a non-JSON Notes string yields an empty envelope.
    """
    translator = HvNotesTranslator()

    envelope = translator.decode(notes_str="this is a free-text note")

    assert envelope.run_id is None
    assert envelope.tags == {}
    return
