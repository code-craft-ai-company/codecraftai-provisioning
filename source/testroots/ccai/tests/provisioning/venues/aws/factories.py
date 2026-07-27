"""
    .. module:: factories
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared fixtures for AWS venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from collections.abc import Generator
from typing import Any

from ccai import testbase

from ccai.credentials.awsaccesskeycredential import AwsAccessKeyCredential
from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
from ccai.provisioning.venues.aws.awsregionconfig import AwsRegionConfig

@testbase.register.resource_factory()
def create_aws__aws_env(constraints=None) -> Generator[Any, None, None]:
    """
        Force a deterministic moto environment for each test.
    """
    saved = {}
    for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
                "AWS_SESSION_TOKEN", "AWS_DEFAULT_REGION"):
        saved[key] = os.environ.get(key, None)

    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

    yield

    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@testbase.register.resource_factory()
def create_aws_credential(constraints=None) -> Generator[AwsAccessKeyCredential, None, None]:
    """
        Return a deterministic AwsAccessKeyCredential.
    """
    rtnval = AwsAccessKeyCredential(
        identifier="aws-test", categories=["aws-access-key"],
        keyid="AKIATEST", secret="secret-value",
    )
    yield rtnval


@testbase.register.resource_factory()
def create_aws_region_config(constraints=None) -> Generator[AwsRegionConfig, None, None]:
    """
        Return a deterministic AwsRegionConfig.
    """
    rtnval = AwsRegionConfig(
        region="us-east-1", availability_zone="us-east-1a",
        default_tags={"ccai:component": "test"},
    )
    yield rtnval


@testbase.register.resource_factory()
def create_aws_venue(constraints=None) -> Generator[CloudVenue, None, None]:
    """
        Return a CloudVenue for tests.
    """
    rtnval = CloudVenue(
        name="aws-test", provider="aws",
        account="test-account",
        region="us-east-1", credential="aws-test",
    )
    yield rtnval


@testbase.register.resource_factory()
def create_aws_aspects(constraints=None) -> Generator[ProvisioningAspects, None, None]:
    """
        Return a ProvisioningAspects bundle for tests.
    """
    rtnval = ProvisioningAspects(runid="testrun01", verify_timeout=30.0,
                                 verify_interval=0.05)
    yield rtnval


@testbase.register.resource_factory()
def create_aws_confirm_aspects(constraints=None) -> Generator[ProvisioningAspects, None, None]:
    """
        Aspects with confirm=True for destroy.
    """
    rtnval = ProvisioningAspects(runid="testrun01", confirm=True,
                                 verify_timeout=30.0, verify_interval=0.05)
    yield rtnval
