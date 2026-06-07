"""
    .. module:: conftest
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared fixtures for AWS venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

import pytest

from ccai.credentials.awsaccesskeycredential import AwsAccessKeyCredential
from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
from ccai.provisioning.venues.aws.awsregionconfig import AwsRegionConfig


@pytest.fixture(autouse=True)
def _aws_env():
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


@pytest.fixture
def credential() -> AwsAccessKeyCredential:
    """
        Return a deterministic AwsAccessKeyCredential.
    """
    rtnval = AwsAccessKeyCredential(
        identifier="aws-test", categories=["aws-access-key"],
        keyid="AKIATEST", secret="secret-value",
    )
    return rtnval


@pytest.fixture
def region_config() -> AwsRegionConfig:
    """
        Return a deterministic AwsRegionConfig.
    """
    rtnval = AwsRegionConfig(
        region="us-east-1", availability_zone="us-east-1a",
        default_tags={"ccai:component": "test"},
    )
    return rtnval


@pytest.fixture
def venue() -> CloudVenue:
    """
        Return a CloudVenue for tests.
    """
    rtnval = CloudVenue(
        name="aws-test", provider="aws",
        account="test-account",
        region="us-east-1", credential="aws-test",
    )
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
        Aspects with confirm=True for destroy.
    """
    rtnval = ProvisioningAspects(runid="testrun01", confirm=True,
                                 verify_timeout=30.0, verify_interval=0.05)
    return rtnval
