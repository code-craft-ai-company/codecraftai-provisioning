"""
    .. module:: test_properties
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Property-based tests for the Equinix Metal venue — idempotent
               apply, inverse destroy, tag round-trip identity.

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
from automojo.credentials.equinixmetalapitokencredential import (
    EquinixMetalApiTokenCredential
)
from automojo.provisioning.venues.equinix_metal.equinixmetalcloudprovisioner import (
    EquinixMetalCloudProvisioner
)
from automojo.provisioning.venues.equinix_metal.metalprojectconfig import (
    MetalProjectConfig
)
from automojo.provisioning.venues.equinix_metal.metaltagtranslator import (
    MetalTagTranslator
)

from ._mockmetalclient import MockMetalClient
from ._specfactory import basic_spec


def _fresh_provisioner(*, with_vpn: bool = False
                       ) -> EquinixMetalCloudProvisioner:
    """
        Build a provisioner with a fresh mock client for each property case.
    """
    venue = CloudVenue(
        name="metal-test", provider="equinix-metal",
        account="proj-test", region="sv", credential="equinix-test",
    )
    credential = EquinixMetalApiTokenCredential(
        identifier="equinix-test", categories=["cloud-venue"],
        token="metal-test-token",
    )
    project_config = MetalProjectConfig(project_id="proj-test", metro="sv")
    spec = basic_spec(with_vpn=with_vpn)
    rtnval = EquinixMetalCloudProvisioner(
        venue=venue, credential=credential, project_config=project_config,
        spec=spec, client=MockMetalClient(project_id="proj-test"),
    )
    return rtnval


# Tag keys / values that survive the "key=value" string encoding.
_tag_key = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789-:.", min_size=1,
    max_size=20,
)
_tag_value = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_.", min_size=0,
    max_size=20,
)


@given(pairs=st.dictionaries(keys=_tag_key, values=_tag_value,
                             min_size=0, max_size=8))
@settings(max_examples=120, deadline=None)
def test_tag_round_trip_identity(pairs) -> None:
    """
        ``from_metal(to_metal(x))`` is the identity (key-sorted).
    """
    neutral = [{key: value} for key, value in pairs.items()]
    encoded = MetalTagTranslator.to_metal(neutral_tags=neutral)
    decoded = MetalTagTranslator.from_metal(strings=encoded)

    expected = [{key: pairs[key]} for key in sorted(pairs.keys())]
    assert decoded == expected
    return


@given(runid=st.text(alphabet="abcdefghij0123456789", min_size=3,
                      max_size=12),
       with_vpn=st.booleans())
@settings(max_examples=40, deadline=None)
def test_apply_idempotent(runid, with_vpn) -> None:
    """
        ``apply ∘ apply`` makes no mutating calls and reports SKIPs.
    """
    aspects = ProvisioningAspects(runid=runid, verify_timeout=5.0,
                                  verify_interval=0.01)
    provisioner = _fresh_provisioner(with_vpn=with_vpn)
    provisioner._client.calls.clear()

    first = provisioner.apply(aspects=aspects)
    assert len(first.created) == 4

    provisioner._client.calls.clear()
    second = provisioner.apply(aspects=aspects)

    assert len(second.created) == 0
    assert set(second.skipped) == {"net-a", "sub-a", "kp-a", "dev-a"}
    assert len(provisioner._client.calls) == 0
    return


@given(runid=st.text(alphabet="abcdefghij0123456789", min_size=3,
                      max_size=12))
@settings(max_examples=40, deadline=None)
def test_destroy_is_inverse_of_apply(runid) -> None:
    """
        ``destroy ∘ apply`` leaves an empty inventory.
    """
    aspects = ProvisioningAspects(runid=runid, verify_timeout=5.0,
                                  verify_interval=0.01)
    confirm = ProvisioningAspects(runid=runid, confirm=True,
                                  verify_timeout=5.0, verify_interval=0.01)
    provisioner = _fresh_provisioner()

    provisioner.apply(aspects=aspects)
    assert len(provisioner.inventory(aspects=aspects)) == 4

    provisioner.destroy(aspects=confirm)
    assert len(provisioner.inventory(aspects=aspects)) == 0
    return
