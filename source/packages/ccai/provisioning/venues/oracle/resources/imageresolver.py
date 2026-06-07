"""
    .. module:: imageresolver
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: CloudImage → OCI image OCID resolver via ComputeClient.list_images.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Any, Dict

from ccai.provisioning.model.cloud.cloudimage import CloudImage
from ccai.provisioning.model.cloud.imagefamily import normalize_family
from ccai.provisioning.venues.oracle.ocisessionfactory import (
    OciSessionFactory
)
from ccai.provisioning.venues.oracle.ocierrors import OciValidationError


# Canonical image family → OCI operating_system string.  Families absent
# from this map pass through verbatim; OCI resolves them live via
# ``list_images``.
_OS_NAMES: Dict[str, str] = {
    "ubuntu": "Canonical Ubuntu",
    "rhel": "Oracle Linux",
    "rocky": "Oracle Linux",
    "almalinux": "Oracle Linux",
    "windows-server": "Windows",
}


def os_name_for(*, family: str) -> str:
    """
        Map a neutral image family to an OCI operating_system string.

        The family is first coerced onto the canonical image vocabulary so
        that aliases resolve consistently with every other venue.

        :param family: Neutral image family (canonical token or alias).

        :returns: An OCI operating_system string.

        :raises: SchemaSemanticError when the family is not canonical.
    """
    canonical_family = normalize_family(value=family)
    family_token = canonical_family.value
    rtnval = _OS_NAMES.get(family_token, family_token)
    return rtnval


class ImageResolver:
    """
        Resolver from a venue-neutral :class:`CloudImage` to an OCI image
        OCID.

        Strategy: call ``ComputeClient.list_images`` filtered by the
        operating-system name and version, and select the newest entry.
    """

    def __init__(self, *, session_factory: OciSessionFactory) -> None:
        """
            Construct an ImageResolver.

            :param session_factory: OciSessionFactory.
        """
        self._session_factory: OciSessionFactory = session_factory
        return

    def _compute(self) -> Any:
        """
            Return the OCI ComputeClient.

            :returns: An ``oci`` ComputeClient.
        """
        rtnval = self._session_factory.client(service_name="compute")
        return rtnval

    def resolve(self, *, image: CloudImage) -> str:
        """
            Resolve the OCI image OCID for the given CloudImage.

            :param image: The neutral CloudImage.

            :returns: The OCI image OCID string.
            :raises: OciValidationError
        """
        client = self._compute()
        compartment_id = self._session_factory.region_config.compartment_id
        os_name = os_name_for(family=image.family)

        list_kwargs: Dict[str, Any] = {}
        list_kwargs["compartment_id"] = compartment_id
        list_kwargs["operating_system"] = os_name
        list_kwargs["operating_system_version"] = image.version
        list_kwargs["sort_by"] = "TIMECREATED"
        list_kwargs["sort_order"] = "DESC"

        try:
            response = client.list_images(**list_kwargs)
        except Exception as xcpt:
            err_msg_lines = ["OCI ImageResolver list_images call failed."]
            err_msg_lines.append("FAMILY: {}".format(image.family))
            err_msg_lines.append("VERSION: {}".format(image.version))
            err_msg_lines.append("CAUSE: {}".format(xcpt))
            err_msg = os.linesep.join(err_msg_lines)
            raise OciValidationError(err_msg) from None

        entries = response.data
        if entries is not None and len(entries) > 0:
            rtnval = getattr(entries[0], "id", "")
            if rtnval is not None and len(rtnval) > 0:
                return rtnval

        err_msg_lines = ["OCI ImageResolver could not resolve a CloudImage."]
        err_msg_lines.append("FAMILY: {}".format(image.family))
        err_msg_lines.append("VERSION: {}".format(image.version))
        err_msg_lines.append("ARCH: {}".format(image.architecture))
        err_msg_lines.append("OS_NAME: {}".format(os_name))
        err_msg = os.linesep.join(err_msg_lines)
        raise OciValidationError(err_msg)
