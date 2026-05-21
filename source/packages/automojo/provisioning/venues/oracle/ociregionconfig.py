"""
    .. module:: ociregionconfig
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: OciRegionConfig — region + compartment + availability domain
               + default tags bundle for the Oracle Cloud venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Dict, List, Optional


class OciRegionConfig:
    """
        Bundle describing where an :class:`OracleCloudProvisioner` operates.

        Holds the OCI region identifier, the apex compartment OCID, the
        default availability domain, and a list of default tags applied to
        every resource the venue creates.  OCI structures everything inside a
        compartment (the hierarchical apex container) and places zonal
        resources inside availability domains.
    """

    def __init__(self, *, region: str, compartment_id: str,
                 availability_domain: str,
                 default_tags: Optional[Dict[str, str]] = None) -> None:
        """
            Construct an OciRegionConfig.

            :param region: OCI region identifier (e.g. ``us-ashburn-1``).
            :param compartment_id: Apex compartment OCID for the run.
            :param availability_domain: Default availability domain
                                        (e.g. ``Uocm:US-ASHBURN-AD-1``).
            :param default_tags: Optional flat dict of tag key/value pairs to
                                 apply to every created resource.

            :raises: ValueError
        """
        if region is None or len(region) == 0:
            raise ValueError("OciRegionConfig.region must not be empty.")

        if compartment_id is None or len(compartment_id) == 0:
            raise ValueError(
                "OciRegionConfig.compartment_id must not be empty."
            )

        if availability_domain is None or len(availability_domain) == 0:
            raise ValueError(
                "OciRegionConfig.availability_domain must not be empty."
            )

        effective_tags = default_tags if default_tags is not None else {}

        self._region: str = region
        self._compartment_id: str = compartment_id
        self._availability_domain: str = availability_domain
        self._default_tags: Dict[str, str] = effective_tags
        return

    @property
    def region(self) -> str:
        """
            Return the OCI region identifier.

            :returns: The region string.
        """
        rtnval = self._region
        return rtnval

    @property
    def compartment_id(self) -> str:
        """
            Return the apex compartment OCID.

            :returns: The compartment OCID string.
        """
        rtnval = self._compartment_id
        return rtnval

    @property
    def availability_domain(self) -> str:
        """
            Return the default availability domain.

            :returns: The availability domain string.
        """
        rtnval = self._availability_domain
        return rtnval

    @property
    def default_tags(self) -> Dict[str, str]:
        """
            Return the list of default tag dicts.

            :returns: A defensive copy of the default tag list.
        """
        rtnval = dict(self._default_tags)
        return rtnval
