"""
    .. module:: conftest
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared fixtures for Equinix Metal venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import pytest

from ccai.credentials.equinixmetalapitokencredential import (
    EquinixMetalApiTokenCredential
)
from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
from ccai.provisioning.venues.equinix_metal.metalprojectconfig import (
    MetalProjectConfig
)

from ._mockmetalclient import MockMetalClient


@pytest.fixture
def credential() -> EquinixMetalApiTokenCredential:
    """
        Return a deterministic EquinixMetalApiTokenCredential.
    """
    rtnval = EquinixMetalApiTokenCredential(
        identifier="equinix-test", categories=["cloud-venue"],
        token="metal-test-token",
    )
    return rtnval


@pytest.fixture
def project_config() -> MetalProjectConfig:
    """
        Return a deterministic MetalProjectConfig.
    """
    rtnval = MetalProjectConfig(
        project_id="proj-test", metro="sv",
        default_tags={"ccai:component": "test"},
    )
    return rtnval


@pytest.fixture
def venue() -> CloudVenue:
    """
        Return a CloudVenue for tests.
    """
    rtnval = CloudVenue(
        name="metal-test", provider="equinix-metal",
        account="proj-test", region="sv", credential="equinix-test",
    )
    return rtnval


@pytest.fixture
def aspects() -> ProvisioningAspects:
    """
        Return a ProvisioningAspects bundle for tests.
    """
    rtnval = ProvisioningAspects(runid="testrun01", verify_timeout=5.0,
                                 verify_interval=0.01)
    return rtnval


@pytest.fixture
def confirm_aspects() -> ProvisioningAspects:
    """
        Aspects with confirm=True for destroy.
    """
    rtnval = ProvisioningAspects(runid="testrun01", confirm=True,
                                 verify_timeout=5.0, verify_interval=0.01)
    return rtnval


@pytest.fixture
def mock_client() -> MockMetalClient:
    """
        Return a fresh deterministic MockMetalClient.
    """
    rtnval = MockMetalClient(project_id="proj-test")
    return rtnval
