"""
    .. module:: doregionconfig
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: DoRegionConfig — DigitalOcean region + default tags bundle.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Dict, List, Optional


# Common DigitalOcean datacenter region slugs.
KNOWN_DO_REGIONS = frozenset({
    "nyc1", "nyc2", "nyc3",
    "ams2", "ams3",
    "sfo1", "sfo2", "sfo3",
    "sgp1",
    "lon1",
    "fra1",
    "tor1",
    "blr1",
    "syd1",
})


class DoRegionConfig:
    """
        Bundle describing where a :class:`DigitalOceanCloudProvisioner`
        operates.

        Holds the DigitalOcean region slug, the Spaces region (which may
        differ from the droplet region), and a list of default tags applied
        to every resource the venue creates.
    """

    def __init__(self, *, region: str,
                 spaces_region: Optional[str] = None,
                 default_tags: Optional[List[Dict[str, str]]] = None) -> None:
        """
            Construct a DoRegionConfig.

            :param region: DigitalOcean region slug (e.g. ``nyc3``).
            :param spaces_region: Optional Spaces region slug; defaults to
                                  ``region`` when omitted.
            :param default_tags: Optional list of single-entry tag dicts to
                                  apply to every created resource.
        """
        if region is None or len(region) == 0:
            raise ValueError("DoRegionConfig.region must not be empty.")

        effective_spaces = spaces_region if spaces_region is not None else region
        effective_tags = default_tags if default_tags is not None else []

        self._region: str = region
        self._spaces_region: str = effective_spaces
        self._default_tags: List[Dict[str, str]] = effective_tags
        return

    @property
    def region(self) -> str:
        """
            Return the DigitalOcean region slug.

            :returns: The region string.
        """
        rtnval = self._region
        return rtnval

    @property
    def spaces_region(self) -> str:
        """
            Return the Spaces region slug.

            :returns: The Spaces region string.
        """
        rtnval = self._spaces_region
        return rtnval

    @property
    def default_tags(self) -> List[Dict[str, str]]:
        """
            Return the list of default tag dicts.

            :returns: A defensive copy of the default tag list.
        """
        rtnval = list(self._default_tags)
        return rtnval
