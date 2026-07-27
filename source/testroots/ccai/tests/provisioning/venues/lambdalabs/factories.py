"""
    .. module:: factories
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared fixtures for Lambda Labs venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from collections.abc import Generator

from ccai import testbase

from ccai.credentials.lambdalabsapikeycredential import (
    LambdalabsApiKeyCredential
)
from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue

@testbase.register.resource_factory()
def create_lambdalabs_credential(constraints=None) -> Generator[LambdalabsApiKeyCredential, None, None]:
    """
        Return a deterministic Lambda Labs API-key credential.
    """
    rtnval = LambdalabsApiKeyCredential(identifier="ll-test",
                                        categories=["hpc-venue"],
                                        token="secret_lambdalabs_test")
    yield rtnval


@testbase.register.resource_factory()
def create_lambdalabs_venue(constraints=None) -> Generator[CloudVenue, None, None]:
    """
        Return a CloudVenue for the Lambda Labs venue tests.
    """
    rtnval = CloudVenue(name="lambdalabs-test", provider="lambdalabs",
                        region="us-east-1", credential="ll-test")
    yield rtnval


@testbase.register.resource_factory()
def create_lambdalabs_aspects(constraints=None) -> Generator[ProvisioningAspects, None, None]:
    """
        Return a ProvisioningAspects bundle for tests.
    """
    rtnval = ProvisioningAspects(runid="testrun01", verify_timeout=30.0,
                                 verify_interval=0.05)
    yield rtnval


@testbase.register.resource_factory()
def create_lambdalabs_confirm_aspects(constraints=None) -> Generator[ProvisioningAspects, None, None]:
    """
        Return ProvisioningAspects with confirm=True for destroy.
    """
    rtnval = ProvisioningAspects(runid="testrun01", confirm=True,
                                 verify_timeout=30.0, verify_interval=0.05)
    yield rtnval
