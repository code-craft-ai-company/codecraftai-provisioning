"""
    .. module:: conftest
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared fixtures for the XCP-ng venue tests.

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

@testbase.register.resource_factory()
def create_xcpng_venue(constraints=None) -> Generator[CloudVenue, None, None]:
    """
        Return a CloudVenue for the XCP-ng venue tests.
    """
    rtnval = CloudVenue(name="xcpng-test", provider="xcpng",
                        endpoint="https://xen-master.lab",
                        region="homelab", credential="xen-cred")
    yield rtnval


@testbase.register.resource_factory()
def create_xcpng_aspects(constraints=None) -> Generator[ProvisioningAspects, None, None]:
    """
        Return a ProvisioningAspects bundle for tests.
    """
    rtnval = ProvisioningAspects(runid="testrun01", verify_timeout=30.0,
                                 verify_interval=0.05)
    yield rtnval


@testbase.register.resource_factory()
def create_xcpng_confirm_aspects(constraints=None) -> Generator[ProvisioningAspects, None, None]:
    """
        Return ProvisioningAspects with confirm=True for destroy.
    """
    rtnval = ProvisioningAspects(runid="testrun01", confirm=True,
                                 verify_timeout=30.0, verify_interval=0.05)
    yield rtnval
