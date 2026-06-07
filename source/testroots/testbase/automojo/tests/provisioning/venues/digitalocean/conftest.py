"""
    .. module:: conftest
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared fixtures for DigitalOcean venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import pytest

from ccai.credentials.digitaloceanapitokencredential import (
    DigitalOceanApiTokenCredential
)
from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
from ccai.provisioning.venues.digitalocean.doclient import (
    DigitalOceanClient
)
from ccai.provisioning.venues.digitalocean.doregionconfig import (
    DoRegionConfig
)

from ._mockclient import MockDigitalOceanRawClient


@pytest.fixture
def credential() -> DigitalOceanApiTokenCredential:
    """
        Return a deterministic DigitalOceanApiTokenCredential.
    """
    rtnval = DigitalOceanApiTokenCredential(
        identifier="do-test", categories=["cloud-venue"],
        token="dop_v1_testtoken",
    )
    return rtnval


@pytest.fixture
def region_config() -> DoRegionConfig:
    """
        Return a deterministic DoRegionConfig.
    """
    rtnval = DoRegionConfig(
        region="nyc3", spaces_region="nyc3",
        default_tags={"ccai:component": "test"},
    )
    return rtnval


@pytest.fixture
def venue() -> CloudVenue:
    """
        Return a CloudVenue for tests.
    """
    rtnval = CloudVenue(
        name="do-test", provider="digitalocean",
        region="nyc3", credential="do-test",
    )
    return rtnval


@pytest.fixture
def raw_client() -> MockDigitalOceanRawClient:
    """
        Return a fresh in-memory mock pydo client.
    """
    rtnval = MockDigitalOceanRawClient()
    return rtnval


@pytest.fixture
def do_client(credential, raw_client) -> DigitalOceanClient:
    """
        Return a DigitalOceanClient wrapping the mock pydo client.
    """
    rtnval = DigitalOceanClient(credential=credential, raw_client=raw_client)
    return rtnval


@pytest.fixture
def aspects() -> ProvisioningAspects:
    """
        Return a ProvisioningAspects bundle for tests.
    """
    rtnval = ProvisioningAspects(runid="dotestrun01", verify_timeout=30.0,
                                 verify_interval=0.05)
    return rtnval


@pytest.fixture
def confirm_aspects() -> ProvisioningAspects:
    """
        Aspects with confirm=True for destroy.
    """
    rtnval = ProvisioningAspects(runid="dotestrun01", confirm=True,
                                 verify_timeout=30.0, verify_interval=0.05)
    return rtnval
