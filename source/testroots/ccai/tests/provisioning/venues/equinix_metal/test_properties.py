"""
    .. module:: test_properties
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Property-based tests for the Equinix Metal venue — idempotent
               apply, inverse destroy, tag round-trip identity.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai.testbase.properties import given
from ccai.testbase.properties import strategies as st

from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
from ccai.credentials.equinixmetalapitokencredential import (
    EquinixMetalApiTokenCredential
)
from ccai.provisioning.venues.equinix_metal.equinixmetalcloudprovisioner import (
    EquinixMetalCloudProvisioner
)
from ccai.provisioning.venues.equinix_metal.metalprojectconfig import (
    MetalProjectConfig
)
from ccai.provisioning.venues.equinix_metal.metaltagtranslator import (
    MetalTagTranslator
)

from ccai.tests.provisioning.venues.equinix_metal._mockmetalclient import MockMetalClient
from ccai.tests.provisioning.venues.equinix_metal._specfactory import basic_spec


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
                             min_size=0, max_size=8), constraints={"max_examples": 120})
def test_tag_round_trip_identity(pairs) -> None:
    """
        ``from_metal(to_metal(x))`` is the identity (key-sorted).
    """
    encoded = MetalTagTranslator.to_metal(neutral_tags=pairs)
    decoded = MetalTagTranslator.from_metal(strings=encoded)

    assert decoded == pairs
    return


@given(runid=st.text(alphabet="abcdefghij0123456789", min_size=3,
                      max_size=12),
       with_vpn=st.booleans(), constraints={"max_examples": 40})
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
                      max_size=12), constraints={"max_examples": 40})
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
