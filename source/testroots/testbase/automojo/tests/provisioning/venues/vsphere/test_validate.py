"""
    .. module:: test_validate
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Validate-table tests for the VSphere venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import pytest

from ccai.provisioning.model.cloud.cloudinterconnect import (
    CloudInterconnect
)
from ccai.provisioning.model.cloud.cloudloadbalancer import (
    CloudLoadBalancer
)
from ccai.provisioning.model.cloud.cloudobjectbucket import (
    CloudObjectBucket
)
from ccai.provisioning.venues.vsphere.vserrors import VsValidationError
from ccai.provisioning.venues.vsphere.vspherecloudprovisioner import (
    VSphereCloudProvisioner
)
from ccai.provisioning.venues.vsphere.vspherevenueconfig import (
    VSphereVenueConfig
)

from ._mockvsphere import MockVSphereOps
from ._specfactory import basic_spec


def _provisioner(*, venue, credential, config, spec):
    """
        Helper: build a provisioner backed by a mock ops facade.
    """
    ops = MockVSphereOps(library_items={"ubuntu-22.04": "item-ubuntu"})
    rtnval = VSphereCloudProvisioner(
        venue=venue, credential=credential, config=config, spec=spec,
        ops=ops,
    )
    return rtnval


def test_validate_accepts_clean_spec(venue, credential, config) -> None:
    """
        A clean spec validates with ok=True.
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               config=config, spec=spec)
    result = provisioner.validate(aspects=None)
    assert result.ok is True
    return


def test_validate_rejects_object_bucket(venue, credential, config) -> None:
    """
        CloudObjectBucket is rejected — vSphere has no object storage.
    """
    spec = basic_spec()
    spec.buckets.append(CloudObjectBucket(name="bkt-a", region="homelab"))
    provisioner = _provisioner(venue=venue, credential=credential,
                               config=config, spec=spec)
    with pytest.raises(VsValidationError) as excinfo:
        provisioner.validate(aspects=None)
    assert "object-storage" in str(excinfo.value)
    return


def test_validate_rejects_interconnect(venue, credential, config) -> None:
    """
        A non-NONE CloudInterconnect is rejected.
    """
    spec = basic_spec()
    spec.instances[0].interconnect = CloudInterconnect(
        kind="EFA", bandwidth_gbps=400, topology="RAIL_OPTIMIZED",
    )
    provisioner = _provisioner(venue=venue, credential=credential,
                               config=config, spec=spec)
    with pytest.raises(VsValidationError) as excinfo:
        provisioner.validate(aspects=None)
    assert "interconnect" in str(excinfo.value)
    return


def test_validate_rejects_lb_without_nsx(venue, credential, config) -> None:
    """
        CloudLoadBalancer is rejected when NSX is absent.
    """
    spec = basic_spec()
    spec.load_balancers.append(CloudLoadBalancer(name="lb-a",
                                                 scheme="internal"))
    provisioner = _provisioner(venue=venue, credential=credential,
                               config=config, spec=spec)
    with pytest.raises(VsValidationError) as excinfo:
        provisioner.validate(aspects=None)
    assert "NSX" in str(excinfo.value)
    return


def test_validate_accepts_lb_with_nsx(venue, credential) -> None:
    """
        CloudLoadBalancer is accepted when NSX is configured.
    """
    config = VSphereVenueConfig(
        host="vcenter.lab", datacenter="DC1", cluster="Cluster1",
        folder="/DC1/vm/ccai", content_library_ids=["lib-1"],
        nsx_available=True, subnet_vlan_ids={"pg-a": 1020},
    )
    spec = basic_spec()
    spec.load_balancers.append(CloudLoadBalancer(name="lb-a",
                                                 scheme="internal"))
    provisioner = _provisioner(venue=venue, credential=credential,
                               config=config, spec=spec)
    result = provisioner.validate(aspects=None)
    assert result.ok is True
    return


def test_validate_rejects_unknown_size(venue, credential, config) -> None:
    """
        An unknown instance size hint is rejected.
    """
    spec = basic_spec(instance_size="gigantic")
    provisioner = _provisioner(venue=venue, credential=credential,
                               config=config, spec=spec)
    with pytest.raises(VsValidationError):
        provisioner.validate(aspects=None)
    return
