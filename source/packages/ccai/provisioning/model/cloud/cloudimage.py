"""
    .. module:: cloudimage
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Venue-neutral image descriptor (family + version + architecture).

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Optional

from ccai.interfaces.schemaobject import SchemaObject
from ccai.interfaces.schemafield import Field

from ccai.interfaces.schemavalidationerror import SchemaValidationError
from ccai.provisioning.model.cloud.imagefamily import (
    ImageArchitecture,
    ImageFamily,
    normalize_architecture,
    normalize_family,
    validate_version,
)


class CloudImage(SchemaObject):
    """
        Venue-neutral image triple.

        A venue resolver converts (family, version, architecture) into an AMI id,
        GCP image family resource, Azure SKU triple, etc.

        The (family, version, architecture) triple is normalized and validated
        against the canonical image vocabulary at construction time so that an
        unsupported request is rejected once, consistently, regardless of venue.
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
            :param version: Image version string (dotted numeric, e.g. 24.04).
            :param architecture: One of x86_64 or arm64 (aliases accepted).
            :param owner: Optional venue-side owner / account / publisher.

            :raises: SchemaValidationError, SchemaSemanticError
        """
        if family is None or len(family) == 0:
            raise SchemaValidationError("family must not be empty.")

        if version is None or len(version) == 0:
            raise SchemaValidationError("version must not be empty.")

        if architecture is None or len(architecture) == 0:
            raise SchemaValidationError("architecture must not be empty.")

        canonical_family = normalize_family(value=family)
        canonical_architecture = normalize_architecture(value=architecture)
        validate_version(version=version)

        super().__init__(family=canonical_family.value, version=version,
                         architecture=canonical_architecture.value,
                         owner=owner)
        return

    @property
    def image_family(self) -> ImageFamily:
        """
            The canonical :class:`ImageFamily` member for this image.

            :returns: The canonical ImageFamily.
        """
        rtnval = normalize_family(value=self.family)
        return rtnval

    @property
    def image_architecture(self) -> ImageArchitecture:
        """
            The canonical :class:`ImageArchitecture` member for this image.

            :returns: The canonical ImageArchitecture.
        """
        rtnval = normalize_architecture(value=self.architecture)
        return rtnval
