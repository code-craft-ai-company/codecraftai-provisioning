"""
    .. module:: test_venue_image_vocabulary
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Cross-venue tests proving each image resolver accepts the
        canonical image-family vocabulary and rejects unsupported families
        with a consistent SchemaSemanticError.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import pytest

from automojo.provisioning.model.cloud.cloudimage import CloudImage
from automojo.provisioning.model.exceptions import SchemaSemanticError

from automojo.provisioning.venues.aws.resources.imageresolver import (
    ImageResolver as AwsImageResolver
)
from automojo.provisioning.venues.azure.resources.imageresolver import (
    ImageResolver as AzureImageResolver
)
from automojo.provisioning.venues.digitalocean.doresolver import DoResolver


class _FakeAwsSessionFactory:
    """
        Minimal AWS session-factory stub.  The supported-family path of the
        resolver short-circuits on the SSM/DescribeImages catalog miss and
        the unsupported-family path never reaches a client call, so the
        client methods only need to exist.
    """

    def client(self, *, service_name: str):
        rtnval = _FakeAwsClient()
        return rtnval


class _FakeAwsClient:
    """
        A fake boto3 client that resolves no images.
    """

    def describe_images(self, **kwargs):
        rtnval = {"Images": []}
        return rtnval

    def get_parameter(self, **kwargs):
        raise RuntimeError("no such parameter")


def test_azure_accepts_canonical_family() -> None:
    resolver = AzureImageResolver()
    image = CloudImage(family="ubuntu", version="24.04",
                       architecture="x86_64")
    reference = resolver.resolve(image=image)
    assert reference["publisher"] == "Canonical"
    return


def test_azure_accepts_canonical_windows_server() -> None:
    resolver = AzureImageResolver()
    image = CloudImage(family="windows-server", version="2022",
                       architecture="x86_64")
    reference = resolver.resolve(image=image)
    assert reference["publisher"] == "MicrosoftWindowsServer"
    return


def test_azure_rejects_unsupported_family() -> None:
    resolver = AzureImageResolver()
    # AlmaLinux is a canonical family the azure resolver does not serve.
    image = CloudImage(family="almalinux", version="9",
                       architecture="x86_64")
    with pytest.raises(SchemaSemanticError) as excinfo:
        resolver.resolve(image=image)
    assert "almalinux" in str(excinfo.value)
    assert "azure" in str(excinfo.value)
    return


def test_digitalocean_accepts_canonical_family() -> None:
    resolver = DoResolver()
    slug = resolver.image_to_slug(family="ubuntu", version="24.04",
                                  architecture="x86_64")
    assert slug == "ubuntu-24-04-x64"
    return


def test_digitalocean_accepts_rocky_alias() -> None:
    resolver = DoResolver()
    # ``rockylinux`` is a recognised alias of the canonical ``rocky``.
    slug = resolver.image_to_slug(family="rockylinux", version="9",
                                  architecture="x86_64")
    assert slug == "rockylinux-9-x64"
    return


def test_digitalocean_rejects_unsupported_family() -> None:
    resolver = DoResolver()
    # Windows Server is a canonical family DigitalOcean droplets cannot run.
    with pytest.raises(SchemaSemanticError) as excinfo:
        resolver.image_to_slug(family="windows-server", version="2022",
                               architecture="x86_64")
    assert "windows-server" in str(excinfo.value)
    assert "digitalocean" in str(excinfo.value)
    return


def test_aws_rejects_unsupported_family() -> None:
    resolver = AwsImageResolver(session_factory=_FakeAwsSessionFactory())
    # Windows Server is a canonical family this AWS resolver does not serve.
    image = CloudImage(family="windows-server", version="2022",
                       architecture="x86_64")
    with pytest.raises(SchemaSemanticError) as excinfo:
        resolver.resolve(image=image)
    assert "windows-server" in str(excinfo.value)
    assert "aws" in str(excinfo.value)
    return


def test_aws_accepts_canonical_family() -> None:
    resolver = AwsImageResolver(session_factory=_FakeAwsSessionFactory())
    image = CloudImage(family="ubuntu", version="24.04",
                       architecture="x86_64")
    # The fake catalog resolves nothing, so a supported family reaches the
    # catalog-miss path rather than the unsupported-family rejection.
    from automojo.provisioning.venues.aws.awserrors import AwsValidationError
    with pytest.raises(AwsValidationError):
        resolver.resolve(image=image)
    return


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
