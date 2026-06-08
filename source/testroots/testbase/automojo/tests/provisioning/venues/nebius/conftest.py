"""
    .. module:: conftest
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared fixtures for the Nebius venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import pytest

from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue

from ._mockclient import MockNebiusClient


@pytest.fixture
def client() -> MockNebiusClient:
    """
        Return a fresh in-memory mock Nebius client.

        :returns: A MockNebiusClient.
    """
    rtnval = MockNebiusClient()
    return rtnval


@pytest.fixture
def venue() -> CloudVenue:
    """
        Return a CloudVenue for the Nebius tests.

        :returns: A CloudVenue.
    """
    rtnval = CloudVenue(
        name="nebius-test", provider="nebius",
        account="proj-test", region="eu-north1",
        credential="nebius-test",
    )
    return rtnval


@pytest.fixture
def aspects() -> ProvisioningAspects:
    """
        Return a ProvisioningAspects bundle for the Nebius tests.

        :returns: A ProvisioningAspects.
    """
    rtnval = ProvisioningAspects(runid="nebrun01")
    return rtnval


@pytest.fixture
def confirm_aspects() -> ProvisioningAspects:
    """
        Return aspects with confirm=True for destroy paths.

        :returns: A ProvisioningAspects.
    """
    rtnval = ProvisioningAspects(runid="nebrun01", confirm=True)
    return rtnval
