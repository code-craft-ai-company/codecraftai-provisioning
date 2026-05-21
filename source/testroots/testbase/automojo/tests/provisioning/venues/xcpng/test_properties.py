"""
    .. module:: test_properties
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Property-based tests for the XCP-ng venue provisioner:
        idempotent apply, destroy-inverts-apply, and tag round-trip
        identity.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from hypothesis import given, settings, strategies as st

from automojo.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from automojo.provisioning.model.cloud.cloudvenue import CloudVenue
from automojo.provisioning.venues.xcpng.xcpngcloudprovisioner import (
    XcpngCloudProvisioner
)
from automojo.provisioning.venues.xcpng.xentagtranslator import (
    XenTagTranslator
)
from automojo.provisioning.venues.xcpng.xcpngspec import XcpngSpec

from automojo.interop.xen.model.xenvm import XenVm

from ._mockclient import MockXenClient, RecordingVpnControlPlane
from ._specfactory import make_instance, make_network


def _venue() -> CloudVenue:
    """
        Build a CloudVenue for the property tests.

        :returns: A CloudVenue instance.
    """
    rtnval = CloudVenue(name="xcpng-prop", provider="xcpng",
                        endpoint="https://xen.lab",
                        region="homelab", credential="xen-cred")
    return rtnval


# Tag keys/values: non-empty, no ``=`` (the tags-list pair delimiter), and
# distinct keys so the round trip is well defined.
_TAG_TEXT = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=122,
                           blacklist_characters="="),
    min_size=1, max_size=12)


@given(repeat_count=st.integers(min_value=2, max_value=5),
       with_vpn=st.booleans(), with_volume=st.booleans())
@settings(deadline=None, max_examples=30)
def test_property_apply_is_idempotent(repeat_count, with_vpn,
                                      with_volume) -> None:
    """
        Applying the same spec any number of times yields exactly one VM;
        every apply after the first creates nothing and skips the instance.
    """
    client = MockXenClient()
    vpn = RecordingVpnControlPlane()
    volumes = []
    if with_volume is True:
        from ._specfactory import make_volume
        volumes = [make_volume()]
    spec = XcpngSpec(networks=[make_network()],
                     instances=[make_instance(with_vpn=with_vpn)],
                     volumes=volumes)
    provisioner = XcpngCloudProvisioner(venue=_venue(), client=client,
                                        spec=spec, vpn_control_plane=vpn)
    aspects = ProvisioningAspects(runid="proprun01")

    first = provisioner.apply(aspects=aspects)
    assert len(first.created) == 1

    for _ in range(repeat_count - 1):
        again = provisioner.apply(aspects=aspects)
        assert len(again.created) == 0
        assert "worker" in again.skipped

    assert len(client.vms) == 1
    assert client.clone_calls == 1
    return


@given(with_vpn=st.booleans(), with_volume=st.booleans())
@settings(deadline=None, max_examples=20)
def test_property_destroy_inverts_apply(with_vpn, with_volume) -> None:
    """
        Destroy after apply returns the venue to its pre-apply VM/VDI state.
    """
    client = MockXenClient()
    vpn = RecordingVpnControlPlane()
    volumes = []
    if with_volume is True:
        from ._specfactory import make_volume
        volumes = [make_volume()]
    spec = XcpngSpec(networks=[make_network()],
                     instances=[make_instance(with_vpn=with_vpn)],
                     volumes=volumes)
    provisioner = XcpngCloudProvisioner(venue=_venue(), client=client,
                                        spec=spec, vpn_control_plane=vpn)
    apply_aspects = ProvisioningAspects(runid="proprun02")
    destroy_aspects = ProvisioningAspects(runid="proprun02", confirm=True)

    vm_count_before = len(client.vms)
    vdi_count_before = len(client.vdis)

    provisioner.apply(aspects=apply_aspects)
    provisioner.destroy(aspects=destroy_aspects)

    assert len(client.vms) == vm_count_before
    assert len(client.vdis) == vdi_count_before
    return


@given(tags=st.lists(
    st.tuples(_TAG_TEXT, _TAG_TEXT), min_size=0, max_size=6,
    unique_by=lambda pair: pair[0]))
def test_property_tag_round_trip_identity(tags) -> None:
    """
        from_xen(to_xen(neutral_tags, run_id)) reproduces the neutral tag
        list as the identity (modulo key ordering, which from_xen sorts).
    """
    translator = XenTagTranslator()
    neutral = {key: value for key, value in tags}

    translated = translator.to_xen(neutral_tags=neutral,
                                   run_id="tag-round-trip")
    vm_record = XenVm(uuid="vm-x", name_label="vm-x",
                      other_config=translated["other_config"],
                      tags=translated["tags"])
    recovered = translator.from_xen(vm_record=vm_record)

    assert recovered == neutral
    return


@given(tags=st.lists(
    st.tuples(_TAG_TEXT, _TAG_TEXT), min_size=0, max_size=6,
    unique_by=lambda pair: pair[0]))
def test_property_tags_list_encodes_key_value_pairs(tags) -> None:
    """
        Each neutral tag is encoded as one key=value entry in the XAPI
        ``tags`` list, and the run-id/owner markers stay out of that list.
    """
    translator = XenTagTranslator()
    neutral = {key: value for key, value in tags}
    translated = translator.to_xen(neutral_tags=neutral, run_id="run-9")

    assert len(translated["tags"]) == len(neutral)
    for key, value in neutral.items():
        assert "{}={}".format(key, value) in translated["tags"]
    return
