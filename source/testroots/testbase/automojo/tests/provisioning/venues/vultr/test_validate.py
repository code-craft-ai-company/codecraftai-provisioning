"""
    .. module:: test_validate
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Validate happy-path and rejection tests for the Vultr venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import pytest

from hypothesis import given, settings
from hypothesis import strategies as st

from automojo.provisioning.model.cloud.cloudinterconnect import (
    CloudInterconnect
)
from automojo.provisioning.model.cloud.cloudsharedfilesystem import (
    CloudSharedFilesystem
)
from automojo.provisioning.venues.vultr.vultrerrors import (
    VultrValidationError
)

from ._specfactory import basic_spec


def test_validate_happy_path(fake_vultr, provisioner_factory, aspects) -> None:
    """
        A baseline spec validates cleanly.
    """
    _fake, client = fake_vultr
    spec = basic_spec()
    provisioner = provisioner_factory(client=client, spec=spec)
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    return


@given(kind=st.sampled_from(["INFINIBAND_HDR", "INFINIBAND_NDR",
                             "INFINIBAND_XDR", "OCI_RDMA", "EFA"]))
@settings(max_examples=10, deadline=None)
def test_validate_rejects_interconnect(kind) -> None:
    """
        Any non-NONE CloudInterconnect kind is a validate error.
    """
    import requests_mock as rmlib

    from automojo.credentials.vultrapikeycredential import (
        VultrApiKeyCredential
    )
    from automojo.provisioning.model.cloud.cloudvenue import CloudVenue
    from automojo.provisioning.venues.vultr.vultrclient import VultrClient
    from automojo.provisioning.venues.vultr.vultrcloudprovisioner import (
        VultrCloudProvisioner
    )

    from ._fakevultr import FakeVultrApi

    interconnect = CloudInterconnect(kind=kind, bandwidth_gbps=200)
    spec = basic_spec(interconnect=interconnect)

    venue = CloudVenue(name="vultr-test", provider="vultr",
                       management_url="https://api.vultr.com",
                       subscription="acct", region="ewr",
                       credential="vultr-test")
    credential = VultrApiKeyCredential(identifier="vultr-test",
                                       categories=["cloud-venue"],
                                       token="test-api-key")
    with rmlib.Mocker() as mocker:
        fake = FakeVultrApi()
        fake.install(adapter=mocker, base_url="https://api.vultr.com/v2")
        client = VultrClient(token="test-api-key",
                             base_url="https://api.vultr.com/v2")
        provisioner = VultrCloudProvisioner(venue=venue,
                                            credential=credential,
                                            spec=spec, client=client)
        with pytest.raises(VultrValidationError):
            provisioner.validate(aspects=None)
    return


@given(kind=st.sampled_from(["LUSTRE", "WEKA", "VAST", "GPFS", "EFS",
                             "FILESTORE"]))
@settings(max_examples=12, deadline=None)
def test_validate_rejects_shared_fs(kind) -> None:
    """
        WEKA/Lustre-class shared filesystems are validate errors.
    """
    import requests_mock as rmlib

    from automojo.credentials.vultrapikeycredential import (
        VultrApiKeyCredential
    )
    from automojo.provisioning.model.cloud.cloudvenue import CloudVenue
    from automojo.provisioning.venues.vultr.vultrclient import VultrClient
    from automojo.provisioning.venues.vultr.vultrcloudprovisioner import (
        VultrCloudProvisioner
    )

    from ._fakevultr import FakeVultrApi

    sfs = CloudSharedFilesystem(name="fs-a", kind=kind, size_tb=10)
    spec = basic_spec(shared_filesystems=[sfs])

    venue = CloudVenue(name="vultr-test", provider="vultr",
                       management_url="https://api.vultr.com",
                       subscription="acct", region="ewr",
                       credential="vultr-test")
    credential = VultrApiKeyCredential(identifier="vultr-test",
                                       categories=["cloud-venue"],
                                       token="test-api-key")
    with rmlib.Mocker() as mocker:
        fake = FakeVultrApi()
        fake.install(adapter=mocker, base_url="https://api.vultr.com/v2")
        client = VultrClient(token="test-api-key",
                             base_url="https://api.vultr.com/v2")
        provisioner = VultrCloudProvisioner(venue=venue,
                                            credential=credential,
                                            spec=spec, client=client)
        with pytest.raises(VultrValidationError):
            provisioner.validate(aspects=None)
    return
