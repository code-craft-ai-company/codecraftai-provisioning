"""
    .. module:: test_properties
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Hypothesis property tests for the Oracle Cloud venue —
               idempotent apply and destroy-is-inverse-of-apply.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from ccai.credentials.oraclecloudapikeycredential import (
    OracleCloudApiKeyCredential
)
from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
from ccai.provisioning.model.cloud.preemptionpolicy import PreemptionPolicy
from ccai.provisioning.venues.oracle.ociregionconfig import OciRegionConfig
from ccai.provisioning.venues.oracle.oraclecloudprovisioner import (
    OracleCloudProvisioner
)

from ._ocifakes import install_fakes
from ._specfactory import basic_spec


_FAKE_KEY = "-----BEGIN PRIVATE KEY-----\nMIIB-fake\n-----END PRIVATE KEY-----\n"


def _make_provisioner(*, spec):
    """
        Build a fully-faked OracleCloudProvisioner for property tests.

        :param spec: An OciSpec.

        :returns: (provisioner, fakes-dict).
    """
    credential = OracleCloudApiKeyCredential(
        identifier="oci-test", categories=["cloud-venue"],
        tenancy_ocid="ocid1.tenancy.oc1..aaaatenancytest",
        user_ocid="ocid1.user.oc1..aaaausertest",
        private_key=_FAKE_KEY,
        fingerprint="aa:bb:cc:dd:ee:ff:00:11:22:33:44:55:66:77:88:99",
    )
    region_config = OciRegionConfig(
        region="us-ashburn-1",
        compartment_id="ocid1.compartment.oc1..aaaacompartmenttest",
        availability_domain="Uocm:US-ASHBURN-AD-1",
    )
    venue = CloudVenue(
        name="oci-test", provider="oracle",
        account="test-tenancy",
        region="us-ashburn-1", credential="oci-test",
    )
    provisioner = OracleCloudProvisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    fakes = install_fakes(provisioner=provisioner)
    rtnval = (provisioner, fakes)
    return rtnval


@settings(max_examples=20, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(with_vpn=st.booleans(),
       preemption=st.sampled_from([PreemptionPolicy.FAIL,
                                   PreemptionPolicy.REACQUIRE,
                                   PreemptionPolicy.BEST_EFFORT]))
def test_apply_idempotent(with_vpn, preemption) -> None:
    """
        apply ∘ apply == apply: the second apply mutates nothing — every
        resource is reported as skipped and the venue inventory is stable.
    """
    spec = basic_spec(with_vpn=with_vpn, preemption=preemption)
    provisioner, fakes = _make_provisioner(spec=spec)
    aspects = ProvisioningAspects(runid="proprun", verify_timeout=5.0,
                                  verify_interval=0.01)

    first = provisioner.apply(aspects=aspects)
    inventory_one = provisioner.inventory(aspects=aspects)

    second = provisioner.apply(aspects=aspects)
    inventory_two = provisioner.inventory(aspects=aspects)

    assert len(first.created) > 0
    # The second apply created nothing tracked as new.
    assert len(second.created) == 0
    # Inventory count is stable across the repeated apply.
    assert len(inventory_one) == len(inventory_two)
    # Only one compute instance exists despite two applies.
    assert len(fakes["compute"].instances) == 1
    return


@settings(max_examples=20, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(with_vpn=st.booleans())
def test_destroy_is_inverse_of_apply(with_vpn) -> None:
    """
        destroy ∘ apply == nop: after destroy the venue inventory is empty.
    """
    spec = basic_spec(with_vpn=with_vpn)
    provisioner, fakes = _make_provisioner(spec=spec)
    aspects = ProvisioningAspects(runid="proprun", verify_timeout=5.0,
                                  verify_interval=0.01)
    confirm = ProvisioningAspects(runid="proprun", confirm=True,
                                  verify_timeout=5.0, verify_interval=0.01)

    provisioner.apply(aspects=aspects)
    assert len(provisioner.inventory(aspects=aspects)) > 0

    provisioner.destroy(aspects=confirm)

    assert len(provisioner.inventory(aspects=aspects)) == 0
    return
