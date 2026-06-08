"""
    .. module:: conftest
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared fixtures for Lambda Labs venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import pytest

from ccai.credentials.lambdalabsapikeycredential import (
    LambdalabsApiKeyCredential
)
from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue


@pytest.fixture
def credential() -> LambdalabsApiKeyCredential:
    """
        Return a deterministic Lambda Labs API-key credential.
    """
    rtnval = LambdalabsApiKeyCredential(identifier="ll-test",
                                        categories=["hpc-venue"],
                                        token="secret_lambdalabs_test")
    return rtnval


@pytest.fixture
def venue() -> CloudVenue:
    """
        Return a CloudVenue for the Lambda Labs venue tests.
    """
    rtnval = CloudVenue(name="lambdalabs-test", provider="lambdalabs",
                        region="us-east-1", credential="ll-test")
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
