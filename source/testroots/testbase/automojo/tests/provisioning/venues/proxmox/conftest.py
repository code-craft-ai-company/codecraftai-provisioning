"""
    .. module:: conftest
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared fixtures for Proxmox VE venue tests.

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


@pytest.fixture
def venue() -> CloudVenue:
    """
        Return a CloudVenue for the Proxmox venue tests.

        :returns: A CloudVenue instance.
    """
    rtnval = CloudVenue(name="proxmox-test", provider="proxmox",
                        endpoint="https://pve.test:8006",
                        region="local", credential="pve-test")
    return rtnval


@pytest.fixture
def aspects() -> ProvisioningAspects:
    """
        Return a ProvisioningAspects bundle for tests.

        :returns: A ProvisioningAspects instance.
    """
    rtnval = ProvisioningAspects(runid="testrun01", verify_timeout=30.0,
                                 verify_interval=0.05)
    return rtnval


@pytest.fixture
def confirm_aspects() -> ProvisioningAspects:
    """
        Return ProvisioningAspects with confirm=True for destroy.

        :returns: A ProvisioningAspects instance with confirm set.
    """
    rtnval = ProvisioningAspects(runid="testrun01", confirm=True,
                                 verify_timeout=30.0, verify_interval=0.05)
    return rtnval
