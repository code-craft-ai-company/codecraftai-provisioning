"""
    .. module:: conftest
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared fixtures for VSphere venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import pytest

from ccai.credentials.vspherecredential import VSphereCredential
from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
from ccai.provisioning.venues.vsphere.vspherevenueconfig import (
    VSphereVenueConfig
)


@pytest.fixture
def credential() -> VSphereCredential:
    """
        Return a deterministic VSphereCredential.
    """
    rtnval = VSphereCredential(
        identifier="vsphere-test", categories=["vm-venue", "vsphere-basic"],
        username="administrator@vsphere.local", password="secret-value",
    )
    return rtnval


@pytest.fixture
def venue() -> CloudVenue:
    """
        Return a CloudVenue for tests.
    """
    rtnval = CloudVenue(
        name="vsphere-test", provider="vsphere",
        endpoint="https://vcenter.lab", region="homelab",
        credential="vsphere-test",
    )
    return rtnval


@pytest.fixture
def config() -> VSphereVenueConfig:
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
    return rtnval


@pytest.fixture
def aspects() -> ProvisioningAspects:
    """
        Return a ProvisioningAspects bundle for tests.
    """
    rtnval = ProvisioningAspects(runid="vsrun01", verify_timeout=30.0,
                                 verify_interval=0.05)
    return rtnval


@pytest.fixture
def confirm_aspects() -> ProvisioningAspects:
    """
        Aspects with confirm=True for destroy.
    """
    rtnval = ProvisioningAspects(runid="vsrun01", confirm=True,
                                 verify_timeout=30.0, verify_interval=0.05)
    return rtnval
