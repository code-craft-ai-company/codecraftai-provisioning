"""
    .. module:: test_validate
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Validate-stage tests for the DigitalOcean venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai import testbase


import pytest

from ccai.provisioning.model.cloud.cloudinterconnect import (
    CloudInterconnect
)
from ccai.provisioning.model.cloud.cloudloadbalancer import (
    CloudLoadBalancer
)
from ccai.interfaces.cloudsharedfilesystem import (
    CloudSharedFilesystem
)
from ccai.provisioning.venues.digitalocean.digitaloceancloudprovisioner import (
    DigitalOceanCloudProvisioner
)
from ccai.provisioning.venues.digitalocean.doerrors import (
    DoValidationError
)

from ._specfactory import basic_spec


def _provisioner(*, venue, credential, region_config, do_client, spec):
    """
        Helper: build a provisioner.
    """
    rtnval = DigitalOceanCloudProvisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec, client=do_client,
    )
    return rtnval


def test_validate_happy_path(venue, credential, region_config, do_client,
                             aspects) -> None:
    """
        A baseline spec validates ok.
    """
    spec = basic_spec()
    provisioner = _provisioner(
        venue=venue, credential=credential, region_config=region_config,
        do_client=do_client, spec=spec,
    )
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    return


@testbase.parametrize("fs_kind", ["LUSTRE", "WEKA", "VAST", "GPFS"])
def test_validate_rejects_unsupported_shared_fs_kinds(
        venue, credential, region_config, do_client, aspects, fs_kind
) -> None:
    """
        WEKA/Lustre-class shared filesystems are rejected with substitution
        guidance.
    """
    spec = basic_spec()
    spec.shared_filesystems.append(CloudSharedFilesystem(
        name="fs-a", kind=fs_kind, size_tb=10,
    ))
    provisioner = _provisioner(
        venue=venue, credential=credential, region_config=region_config,
        do_client=do_client, spec=spec,
    )
    with pytest.raises(DoValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "shared-FS" in str(excinfo.value)
    return


def test_validate_rejects_interconnect_requests(
        venue, credential, region_config, do_client, aspects
) -> None:
    """
        A non-NONE HPC interconnect is a validate-error.
    """
    interconnect = CloudInterconnect(kind="INFINIBAND_NDR",
                                     bandwidth_gbps=400)
    spec = basic_spec()
    spec.instances[0].interconnect = interconnect
    provisioner = _provisioner(
        venue=venue, credential=credential, region_config=region_config,
        do_client=do_client, spec=spec,
    )
    with pytest.raises(DoValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "interconnect" in str(excinfo.value)
    return


def test_validate_warns_on_load_balancer(
        venue, credential, region_config, do_client, aspects
) -> None:
    """
        A CloudLoadBalancer is accepted but emits a v1.5-stub warning.
    """
    spec = basic_spec()
    spec.load_balancers.append(CloudLoadBalancer(
        name="lb-a", scheme="internet-facing",
    ))
    provisioner = _provisioner(
        venue=venue, credential=credential, region_config=region_config,
        do_client=do_client, spec=spec,
    )
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    assert len(result.warnings) == 1
    return


def test_validate_rejects_unknown_region(
        venue, credential, region_config, do_client, aspects
) -> None:
    """
        An unknown DigitalOcean region slug on a VPC is rejected.
    """
    spec = basic_spec()
    spec.networks[0].region = "atlantis1"
    provisioner = _provisioner(
        venue=venue, credential=credential, region_config=region_config,
        do_client=do_client, spec=spec,
    )
    with pytest.raises(DoValidationError):
        provisioner.validate(aspects=aspects)
    return


def test_validate_rejects_unmapped_gpu(
        venue, credential, region_config, do_client, aspects
) -> None:
    """
        An accelerator with no DigitalOcean GPU droplet is rejected.
    """
    from ccai.interfaces.cloudacceleratorspec import (
        CloudAcceleratorSpec
    )
    accel = CloudAcceleratorSpec(kind="GPU", model="MI300X", count=8,
                                 interconnect="NVSWITCH", memory_gb=192)
    spec = basic_spec(accelerators=[accel])
    provisioner = _provisioner(
        venue=venue, credential=credential, region_config=region_config,
        do_client=do_client, spec=spec,
    )
    with pytest.raises(DoValidationError):
        provisioner.validate(aspects=aspects)
    return
