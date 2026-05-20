"""
    .. module:: cloudimage
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Venue-neutral image descriptor (family + version + architecture).

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Optional

from automojo.restclient.base.schemaobject import SchemaObject
from automojo.restclient.base.schemafield import Field

from automojo.provisioning.model.exceptions import SchemaValidationError


_SUPPORTED_ARCHITECTURES = ("x86_64", "arm64")


class CloudImage(SchemaObject):
    """
        Venue-neutral image triple.

        A venue resolver converts (family, version, architecture) into an AMI id,
        GCP image family resource, Azure SKU triple, etc.
    """

    family = Field(str, required=True)
    version = Field(str, required=True)
    architecture = Field(str, required=True)
    owner = Field(str, required=False, default=None)

    def __init__(self, *, family: str, version: str, architecture: str,
                 owner: Optional[str] = None) -> None:
        """
            Construct a CloudImage.

            :param family: Image family (ubuntu, debian, rhel, windows-server, ...).
            :param version: Image version string.
            :param architecture: One of x86_64 or arm64.
            :param owner: Optional venue-side owner / account / publisher.

            :raises: SchemaValidationError
        """
        if family is None or len(family) == 0:
            raise SchemaValidationError("family must not be empty.")

        if version is None or len(version) == 0:
            raise SchemaValidationError("version must not be empty.")

        if architecture not in _SUPPORTED_ARCHITECTURES:
            raise SchemaValidationError(
                "architecture must be one of {}, got {!r}".format(
                    ", ".join(_SUPPORTED_ARCHITECTURES), architecture
                )
            )

        super().__init__(family=family, version=version,
                         architecture=architecture, owner=owner)
        return
