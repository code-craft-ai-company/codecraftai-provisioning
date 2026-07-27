"""
    .. module:: conftest
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared fixtures for libvirt venue tests.

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
def create_libvirt_venue(constraints=None) -> Generator[CloudVenue, None, None]:
    """
        Return a CloudVenue for the libvirt venue tests.
    """
    rtnval = CloudVenue(name="libvirt-test", provider="libvirt",
                        endpoint="qemu:///system",
                        region="local", credential="lv-test")
    yield rtnval


@testbase.register.resource_factory()
def create_libvirt_aspects(constraints=None) -> Generator[ProvisioningAspects, None, None]:
    """
        Return a ProvisioningAspects bundle for tests.
    """
    rtnval = ProvisioningAspects(runid="testrun01", verify_timeout=30.0,
                                 verify_interval=0.05)
    yield rtnval


@testbase.register.resource_factory()
def create_libvirt_confirm_aspects(constraints=None) -> Generator[ProvisioningAspects, None, None]:
    """
        Return ProvisioningAspects with confirm=True for destroy.
    """
    rtnval = ProvisioningAspects(runid="testrun01", confirm=True,
                                 verify_timeout=30.0, verify_interval=0.05)
    yield rtnval
