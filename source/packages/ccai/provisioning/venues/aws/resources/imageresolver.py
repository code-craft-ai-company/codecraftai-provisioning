"""
    .. module:: imageresolver
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: CloudImage → AMI resolver via SSM Parameter Store + DescribeImages.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Dict, Optional

from ccai.provisioning.model.cloud.cloudimage import CloudImage
from ccai.provisioning.model.cloud.imagefamily import normalize_family
from ccai.interfaces.schemasemanticerror import SchemaSemanticError
from ccai.provisioning.venues.aws.awsboto3sessionfactory import (
    AwsBoto3SessionFactory
)
from ccai.provisioning.venues.aws.awserrors import AwsValidationError


# Canonical SSM parameter prefixes per family (where available).
_SSM_PREFIXES: Dict[str, str] = {
    "amazon-linux": "/aws/service/ami-amazon-linux-latest",
    "ubuntu": "/aws/service/canonical/ubuntu/server",
    "debian": "/aws/service/debian/release",
    "rhel": "/aws/service/marketplace/prod-redhat",
}

# DescribeImages owner ids per family (fallback path).
_AMI_OWNERS: Dict[str, str] = {
    "amazon-linux": "amazon",
    "ubuntu": "099720109477",
    "debian": "136693071363",
    "rhel": "309956199498",
}

# Name pattern templates per (family, arch).  ``{version}`` substitution only.
_NAME_PATTERNS: Dict[str, str] = {
    "ubuntu": (
        "ubuntu/images/hvm-ssd/ubuntu-*-{version}-{arch}-server-*"
    ),
    "debian": "debian-{version}-{arch}-*",
    "rhel": "RHEL-{version}*_HVM-*-{arch}-*",
    "amazon-linux": "amzn2-ami-hvm-*-{arch}-gp2",
}

# Canonical image families the AWS resolver can serve.
_SUPPORTED_FAMILIES = frozenset(_AMI_OWNERS.keys())


class ImageResolver:
    """
        Resolver from a venue-neutral :class:`CloudImage` to an AWS AMI id.

        Strategy:

        1. Try SSM Parameter Store with the family-conventional prefix.
        2. Fall back to ``ec2.describe_images`` with the owner + name pattern.
        3. Raise :class:`AwsValidationError` if neither path resolves.
    """

    def __init__(self, *, session_factory: AwsBoto3SessionFactory) -> None:
        """
            Construct an ImageResolver.

            :param session_factory: AwsBoto3SessionFactory.
        """
        self._session_factory: AwsBoto3SessionFactory = session_factory
        return

    def resolve(self, *, image: CloudImage) -> str:
        """
            Resolve the AMI id for the given CloudImage.

            :param image: The neutral CloudImage.

            :returns: The AMI id string.
            :raises: AwsValidationError, SchemaSemanticError
        """
        canonical_family = normalize_family(value=image.family)
        family = canonical_family.value
        version = image.version
        arch = image.architecture

        if family not in _SUPPORTED_FAMILIES:
            supported = ", ".join(sorted(_SUPPORTED_FAMILIES))
            err_msg_lines = ["The aws venue does not support the image "
                             "family."]
            err_msg_lines.append("VENUE: aws")
            err_msg_lines.append("FAMILY: {}".format(family))
            err_msg_lines.append("SUPPORTED: {}".format(supported))
            err_msg = os.linesep.join(err_msg_lines)
            raise SchemaSemanticError(err_msg)

        ami_id = self._try_describe_images(family=family, version=version,
                                           arch=arch)
        if ami_id is not None and len(ami_id) > 0:
            rtnval = ami_id
            return rtnval

        ami_id = self._try_ssm(family=family, version=version, arch=arch)
        if ami_id is not None and len(ami_id) > 0:
            rtnval = ami_id
            return rtnval

        err_msg_lines = ["AWS ImageResolver could not resolve a CloudImage."]
        err_msg_lines.append("FAMILY: {}".format(family))
        err_msg_lines.append("VERSION: {}".format(version))
        err_msg_lines.append("ARCH: {}".format(arch))
        err_msg = os.linesep.join(err_msg_lines)
        raise AwsValidationError(err_msg)

    def _try_describe_images(self, *, family: str, version: str,
                             arch: str) -> Optional[str]:
        """
            Attempt to find an AMI via ``describe_images``.

            Tries the canonical x86_64/arm64 arch first, then falls back to
            the alias ``amd64`` (older Ubuntu AMI naming convention).

            :param family: Image family name.
            :param version: Image version.
            :param arch: Architecture string.

            :returns: An AMI id or None.
        """
        pattern = _NAME_PATTERNS.get(family, None)
        owner = _AMI_OWNERS.get(family, None)
        if pattern is None or owner is None:
            rtnval: Optional[str] = None
            return rtnval

        arch_aliases = [arch]
        if arch == "x86_64":
            arch_aliases.append("amd64")

        client = self._session_factory.client(service_name="ec2")
        for arch_candidate in arch_aliases:
            name_pattern = pattern.format(version=version,
                                          arch=arch_candidate)
            try:
                response = client.describe_images(
                    Owners=[owner],
                    Filters=[{"Name": "name", "Values": [name_pattern]}],
                )
            except Exception:
                continue

            images = response.get("Images", [])
            if len(images) == 0:
                continue
            images.sort(key=lambda img: img.get("CreationDate", ""),
                        reverse=True)
            rtnval = images[0].get("ImageId", None)
            return rtnval

        # Last-resort: glob across versions for this family.
        loose_pattern = pattern.replace("{version}", "*").replace(
            "{arch}", "*"
        )
        try:
            response = client.describe_images(
                Owners=[owner],
                Filters=[{"Name": "name", "Values": [loose_pattern]}],
            )
        except Exception:
            rtnval = None
            return rtnval

        images = response.get("Images", [])
        if len(images) == 0:
            rtnval = None
            return rtnval

        images.sort(key=lambda img: img.get("CreationDate", ""), reverse=True)
        rtnval = images[0].get("ImageId", None)
        return rtnval

    def _try_ssm(self, *, family: str, version: str,
                 arch: str) -> Optional[str]:
        """
            Attempt to find an AMI via SSM Parameter Store.

            :param family: Image family name.
            :param version: Image version.
            :param arch: Architecture string.

            :returns: An AMI id or None.
        """
        prefix = _SSM_PREFIXES.get(family, None)
        if prefix is None:
            rtnval: Optional[str] = None
            return rtnval

        if family == "amazonlinux":
            param = "{}/amzn2-ami-hvm-{}-gp2".format(prefix, arch)
        elif family == "ubuntu":
            param = "{}/{}/stable/current/{}/hvm/ebs-gp2/ami-id".format(
                prefix, version, arch
            )
        else:
            param = "{}/{}/latest/ami-id".format(prefix, version)

        client = self._session_factory.client(service_name="ssm")
        try:
            response = client.get_parameter(Name=param)
        except Exception:
            rtnval = None
            return rtnval

        rtnval = response.get("Parameter", {}).get("Value", None)
        return rtnval
