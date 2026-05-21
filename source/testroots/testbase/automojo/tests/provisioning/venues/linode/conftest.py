"""
    .. module:: conftest
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared fixtures for the Linode venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import pytest

from automojo.credentials.linodeapitokencredential import (
    LinodeApiTokenCredential
)
from automojo.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from automojo.provisioning.model.cloud.cloudvenue import CloudVenue
from automojo.provisioning.venues.linode.linoderegionconfig import (
    LinodeRegionConfig
)

from ._mocklinodeclient import MockLinodeClient


@pytest.fixture
def credential() -> LinodeApiTokenCredential:
    """
        Return a deterministic LinodeApiTokenCredential.
    """
    rtnval = LinodeApiTokenCredential(
        identifier="linode-test", categories=["cloud-venue"],
        token="linode-token-value",
    )
    return rtnval


@pytest.fixture
def region_config() -> LinodeRegionConfig:
    """
        Return a deterministic LinodeRegionConfig.
    """
    rtnval = LinodeRegionConfig(
        region="us-east", object_storage_cluster="us-east-1",
        default_tags={"automojo:component": "test"},
    )
    return rtnval


@pytest.fixture
def venue() -> CloudVenue:
    """
        Return a CloudVenue for tests.
    """
    rtnval = CloudVenue(
        name="linode-test", provider="linode",
        region="us-east", credential="linode-test",
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


@pytest.fixture
def mock_client() -> MockLinodeClient:
    """
        Return a fresh MockLinodeClient.
    """
    rtnval = MockLinodeClient()
    return rtnval
