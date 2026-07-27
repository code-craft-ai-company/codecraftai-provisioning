"""
    .. module:: test_properties
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Hypothesis property tests for the Hetzner venue —
               idempotent apply, inverse destroy, label round-trip.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai.testbase.properties import given
from ccai.testbase.properties import strategies as st

from ccai.credentials.hetznerapitokencredential import (
    HetznerApiTokenCredential
)
from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
from ccai.provisioning.venues.hetzner.hetznercloudprovisioner import (
    HetznerCloudProvisioner
)
from ccai.provisioning.venues.hetzner.hetznerlabeltranslator import (
    HetznerLabelTranslator
)
from ccai.provisioning.venues.hetzner.hetznerlocationconfig import (
    HetznerLocationConfig
)

from ccai.tests.provisioning.venues.hetzner._mockclient import MockHetznerClient
from ccai.tests.provisioning.venues.hetzner._specfactory import basic_spec


def _build_provisioner(*, client: MockHetznerClient, with_vpn: bool
                       ) -> HetznerCloudProvisioner:
    """
        Build a HetznerCloudProvisioner over a fresh mock client.
    """
    credential = HetznerApiTokenCredential(
        identifier="hetzner-test", categories=["cloud-venue"],
        token="test-token")
    location_config = HetznerLocationConfig(location="nbg1")
    venue = CloudVenue(name="hetzner-test", provider="hetzner",
                       region="nbg1", credential="hetzner-test")
    spec = basic_spec(with_vpn=with_vpn, with_volume=True)
    rtnval = HetznerCloudProvisioner(
        venue=venue, credential=credential,
        location_config=location_config, spec=spec, client=client)
    return rtnval


@given(with_vpn=st.booleans(), constraints={"max_examples": 25})
def test_apply_idempotent(with_vpn: bool) -> None:
    """
        apply ∘ apply == apply: the second apply mutates nothing.
    """
    client = MockHetznerClient()
    provisioner = _build_provisioner(client=client, with_vpn=with_vpn)
    aspects = ProvisioningAspects(runid="testrun01")

    provisioner.apply(aspects=aspects)
    inventory_first = provisioner.inventory(aspects=aspects)
    creates_after_first = client.create_calls

    provisioner.apply(aspects=aspects)
    inventory_second = provisioner.inventory(aspects=aspects)

    assert client.create_calls == creates_after_first
    assert len(inventory_first) == len(inventory_second)
    return


@given(with_vpn=st.booleans(), constraints={"max_examples": 25})
def test_destroy_is_inverse_of_apply(with_vpn: bool) -> None:
    """
        destroy ∘ apply == nop: the venue is empty after destroy.
    """
    client = MockHetznerClient()
    provisioner = _build_provisioner(client=client, with_vpn=with_vpn)
    aspects = ProvisioningAspects(runid="testrun01", confirm=True)

    provisioner.apply(aspects=aspects)
    provisioner.destroy(aspects=aspects)

    inventory_after = provisioner.inventory(aspects=aspects)
    assert len(inventory_after) == 0
    return


_KEY_PART = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_",
    min_size=1, max_size=20,
).filter(lambda s: s[0].isalnum() and s[-1].isalnum())

_VALUE_PART = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_.",
    min_size=1, max_size=20,
).filter(lambda s: s[0].isalnum() and s[-1].isalnum())


@given(pairs=st.lists(
    st.tuples(_KEY_PART, _VALUE_PART), min_size=0, max_size=8,
    unique_by=lambda t: t[0]), constraints={"max_examples": 60})
def test_label_round_trip_identity_for_conformant_inputs(pairs) -> None:
    """
        from_hetzner(to_hetzner(x)) == sorted(x) for conformant inputs.
    """
    neutral = {key: value for key, value in pairs}
    labels = HetznerLabelTranslator.to_hetzner(neutral_tags=neutral)
    recovered = HetznerLabelTranslator.from_hetzner(labels=labels)

    assert recovered == neutral
    return
