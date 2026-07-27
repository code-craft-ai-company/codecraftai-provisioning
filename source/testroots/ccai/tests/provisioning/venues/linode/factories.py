"""
    .. module:: conftest
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared fixtures for the Linode venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from collections.abc import Generator

from ccai import testbase

from ccai.credentials.linodeapitokencredential import (
    LinodeApiTokenCredential
)
from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
from ccai.provisioning.venues.linode.linoderegionconfig import (
    LinodeRegionConfig
)

from ._mocklinodeclient import MockLinodeClient

@testbase.register.resource_factory()
def create_linode_credential(constraints=None) -> Generator[LinodeApiTokenCredential, None, None]:
    """
        Return a deterministic LinodeApiTokenCredential.
    """
    rtnval = LinodeApiTokenCredential(
        identifier="linode-test", categories=["cloud-venue"],
        token="linode-token-value",
    )
    yield rtnval


@testbase.register.resource_factory()
def create_linode_region_config(constraints=None) -> Generator[LinodeRegionConfig, None, None]:
    """
        Return a deterministic LinodeRegionConfig.
    """
    rtnval = LinodeRegionConfig(
        region="us-east", object_storage_cluster="us-east-1",
        default_tags={"ccai:component": "test"},
    )
    yield rtnval


@testbase.register.resource_factory()
def create_linode_venue(constraints=None) -> Generator[CloudVenue, None, None]:
    """
        Return a CloudVenue for tests.
    """
    rtnval = CloudVenue(
        name="linode-test", provider="linode",
        region="us-east", credential="linode-test",
    )
    yield rtnval


@testbase.register.resource_factory()
def create_linode_aspects(constraints=None) -> Generator[ProvisioningAspects, None, None]:
    """
        Return a ProvisioningAspects bundle for tests.
    """
    rtnval = ProvisioningAspects(runid="testrun01", verify_timeout=30.0,
                                 verify_interval=0.05)
    yield rtnval


@testbase.register.resource_factory()
def create_linode_confirm_aspects(constraints=None) -> Generator[ProvisioningAspects, None, None]:
    """
        Aspects with confirm=True for destroy.
    """
    rtnval = ProvisioningAspects(runid="testrun01", confirm=True,
                                 verify_timeout=30.0, verify_interval=0.05)
    yield rtnval


@testbase.register.resource_factory()
def create_linode_mock_client(constraints=None) -> Generator[MockLinodeClient, None, None]:
    """
        Return a fresh MockLinodeClient.
    """
    rtnval = MockLinodeClient()
    yield rtnval
