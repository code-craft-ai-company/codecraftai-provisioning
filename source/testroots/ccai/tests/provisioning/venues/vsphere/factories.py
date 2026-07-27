"""
    .. module:: factories
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared fixtures for VSphere venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from collections.abc import Generator

from ccai import testbase

from ccai.credentials.vspherecredential import VSphereCredential
from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
from ccai.provisioning.venues.vsphere.vspherevenueconfig import (
    VSphereVenueConfig
)

@testbase.register.resource_factory()
def create_vsphere_credential(constraints=None) -> Generator[VSphereCredential, None, None]:
    """
        Return a deterministic VSphereCredential.
    """
    rtnval = VSphereCredential(
        identifier="vsphere-test", categories=["vm-venue", "vsphere-basic"],
        username="administrator@vsphere.local", password="secret-value",
    )
    yield rtnval


@testbase.register.resource_factory()
def create_vsphere_venue(constraints=None) -> Generator[CloudVenue, None, None]:
    """
        Return a CloudVenue for tests.
    """
    rtnval = CloudVenue(
        name="vsphere-test", provider="vsphere",
        endpoint="https://vcenter.lab", region="homelab",
        credential="vsphere-test",
    )
    yield rtnval


@testbase.register.resource_factory()
def create_vsphere_config(constraints=None) -> Generator[VSphereVenueConfig, None, None]:
    """
        Return a VSphereVenueConfig with a content library and VLAN mapping.
    """
    rtnval = VSphereVenueConfig(
        host="vcenter.lab", datacenter="DC1", cluster="Cluster1",
        folder="/DC1/vm/ccai",
        content_library_ids=["lib-1"],
        template_folder="/DC1/vm/templates",
        nsx_available=False,
        subnet_vlan_ids={"pg-a": 1020},
        default_tags={"ccai:component": "test"},
    )
    yield rtnval


@testbase.register.resource_factory()
def create_vsphere_aspects(constraints=None) -> Generator[ProvisioningAspects, None, None]:
    """
        Return a ProvisioningAspects bundle for tests.
    """
    rtnval = ProvisioningAspects(runid="vsrun01", verify_timeout=30.0,
                                 verify_interval=0.05)
    yield rtnval


@testbase.register.resource_factory()
def create_vsphere_confirm_aspects(constraints=None) -> Generator[ProvisioningAspects, None, None]:
    """
        Aspects with confirm=True for destroy.
    """
    rtnval = ProvisioningAspects(runid="vsrun01", confirm=True,
                                 verify_timeout=30.0, verify_interval=0.05)
    yield rtnval
