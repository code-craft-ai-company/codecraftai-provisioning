"""
    .. module:: conftest
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared fixtures for the Oracle Cloud venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import pytest

from automojo.credentials.oraclecloudapikeycredential import (
    OracleCloudApiKeyCredential
)
from automojo.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from automojo.provisioning.model.cloud.cloudvenue import CloudVenue
from automojo.provisioning.venues.oracle.ociregionconfig import OciRegionConfig


_FAKE_PRIVATE_KEY = (
    "-----BEGIN PRIVATE KEY-----\n"
    "MIIBVgIBADANBgkqhkiG9w0BAQEFAASCAUAwggE8AgEAAkEA-fake-test-key\n"
    "-----END PRIVATE KEY-----\n"
)


@pytest.fixture
def credential() -> OracleCloudApiKeyCredential:
    """
        Return a deterministic OracleCloudApiKeyCredential.
    """
    rtnval = OracleCloudApiKeyCredential(
        identifier="oci-test", categories=["cloud-venue"],
        tenancy_ocid="ocid1.tenancy.oc1..aaaatenancytest",
        user_ocid="ocid1.user.oc1..aaaausertest",
        private_key=_FAKE_PRIVATE_KEY,
        fingerprint="aa:bb:cc:dd:ee:ff:00:11:22:33:44:55:66:77:88:99",
    )
    return rtnval


@pytest.fixture
def region_config() -> OciRegionConfig:
    """
        Return a deterministic OciRegionConfig.
    """
    rtnval = OciRegionConfig(
        region="us-ashburn-1",
        compartment_id="ocid1.compartment.oc1..aaaacompartmenttest",
        availability_domain="Uocm:US-ASHBURN-AD-1",
        default_tags={"automojo_component": "test"},
    )
    return rtnval


@pytest.fixture
def venue() -> CloudVenue:
    """
        Return a CloudVenue for the Oracle tests.
    """
    rtnval = CloudVenue(
        name="oci-test", provider="oracle",
        account="test-tenancy",
        region="us-ashburn-1", credential="oci-test",
    )
    return rtnval


@pytest.fixture
def aspects() -> ProvisioningAspects:
    """
        Return a ProvisioningAspects bundle for tests.
    """
    rtnval = ProvisioningAspects(runid="testrun01", verify_timeout=30.0,
                                 verify_interval=0.05)
    return rtnval


@pytest.fixture
def confirm_aspects() -> ProvisioningAspects:
    """
        Aspects with confirm=True for destroy.
    """
    rtnval = ProvisioningAspects(runid="testrun01", confirm=True,
                                 verify_timeout=30.0, verify_interval=0.05)
    return rtnval
