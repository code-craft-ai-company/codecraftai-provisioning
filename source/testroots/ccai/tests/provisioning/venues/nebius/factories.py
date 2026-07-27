"""
    .. module:: factories
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared fixtures for the Nebius venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from collections.abc import Generator

from ccai import testbase

from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue

from ccai.tests.provisioning.venues.nebius._mockclient import MockNebiusClient

@testbase.register.resource_factory()
def create_nebius_client(constraints=None) -> Generator[MockNebiusClient, None, None]:
    """
        Return a fresh in-memory mock Nebius client.

        :returns: A MockNebiusClient.
    """
    rtnval = MockNebiusClient()
    yield rtnval


@testbase.register.resource_factory()
def create_nebius_venue(constraints=None) -> Generator[CloudVenue, None, None]:
    """
        Return a CloudVenue for the Nebius tests.

        :returns: A CloudVenue.
    """
    rtnval = CloudVenue(
        name="nebius-test", provider="nebius",
        account="proj-test", region="eu-north1",
        credential="nebius-test",
    )
    yield rtnval


@testbase.register.resource_factory()
def create_nebius_aspects(constraints=None) -> Generator[ProvisioningAspects, None, None]:
    """
        Return a ProvisioningAspects bundle for the Nebius tests.

        :returns: A ProvisioningAspects.
    """
    rtnval = ProvisioningAspects(runid="nebrun01")
    yield rtnval


@testbase.register.resource_factory()
def create_nebius_confirm_aspects(constraints=None) -> Generator[ProvisioningAspects, None, None]:
    """
        Return aspects with confirm=True for destroy paths.

        :returns: A ProvisioningAspects.
    """
    rtnval = ProvisioningAspects(runid="nebrun01", confirm=True)
    yield rtnval
