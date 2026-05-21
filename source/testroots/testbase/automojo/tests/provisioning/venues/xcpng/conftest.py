"""
    .. module:: conftest
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared fixtures for the XCP-ng venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import pytest

from automojo.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from automojo.provisioning.model.cloud.cloudvenue import CloudVenue


@pytest.fixture
def venue() -> CloudVenue:
    """
        Return a CloudVenue for the XCP-ng venue tests.
    """
    rtnval = CloudVenue(name="xcpng-test", provider="xcpng",
                        endpoint="https://xen-master.lab",
                        region="homelab", credential="xen-cred")
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
        Return ProvisioningAspects with confirm=True for destroy.
    """
    rtnval = ProvisioningAspects(runid="testrun01", confirm=True,
                                 verify_timeout=30.0, verify_interval=0.05)
    return rtnval
