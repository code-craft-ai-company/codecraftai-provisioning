"""
    .. module:: conftest
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared fixtures for the Oracle Cloud venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from collections.abc import Generator

from ccai import testbase

from ccai.credentials.oraclecloudapikeycredential import (
    OracleCloudApiKeyCredential
)
from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
from ccai.provisioning.venues.oracle.ociregionconfig import OciRegionConfig


_FAKE_PRIVATE_KEY = (
    "-----BEGIN PRIVATE KEY-----\n"
    "MIIBVgIBADANBgkqhkiG9w0BAQEFAASCAUAwggE8AgEAAkEA-fake-test-key\n"
    "-----END PRIVATE KEY-----\n"
)

@testbase.register.resource_factory()
def create_oracle_credential(constraints=None) -> Generator[OracleCloudApiKeyCredential, None, None]:
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
    yield rtnval


@testbase.register.resource_factory()
def create_oracle_region_config(constraints=None) -> Generator[OciRegionConfig, None, None]:
    """
        Return a deterministic OciRegionConfig.
    """
    rtnval = OciRegionConfig(
        region="us-ashburn-1",
        compartment_id="ocid1.compartment.oc1..aaaacompartmenttest",
        availability_domain="Uocm:US-ASHBURN-AD-1",
        default_tags={"ccai_component": "test"},
    )
    yield rtnval


@testbase.register.resource_factory()
def create_oracle_venue(constraints=None) -> Generator[CloudVenue, None, None]:
    """
        Return a CloudVenue for the Oracle tests.
    """
    rtnval = CloudVenue(
        name="oci-test", provider="oracle",
        account="test-tenancy",
        region="us-ashburn-1", credential="oci-test",
    )
    yield rtnval


@testbase.register.resource_factory()
def create_oracle_aspects(constraints=None) -> Generator[ProvisioningAspects, None, None]:
    """
        Return a ProvisioningAspects bundle for tests.
    """
    rtnval = ProvisioningAspects(runid="testrun01", verify_timeout=30.0,
                                 verify_interval=0.05)
    yield rtnval


@testbase.register.resource_factory()
def create_oracle_confirm_aspects(constraints=None) -> Generator[ProvisioningAspects, None, None]:
    """
        Aspects with confirm=True for destroy.
    """
    rtnval = ProvisioningAspects(runid="testrun01", confirm=True,
                                 verify_timeout=30.0, verify_interval=0.05)
    yield rtnval
