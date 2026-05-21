"""
    .. module:: gcpregionconfig
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: GcpRegionConfig — project + region + zone + default labels.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Dict, Optional


# Zones known to host compact-placement-capable A3 families in this venue
# model.  Used by validate to fail early when a zone cannot host A3 training.
_A3_COMPACT_ZONES = frozenset({
    "us-central1-a", "us-central1-b", "us-central1-c",
    "us-east5-a", "us-east5-b", "us-east5-c",
    "europe-west4-a", "europe-west4-b", "europe-west4-c",
    "asia-northeast1-a", "asia-northeast1-b",
})


class GcpRegionConfig:
    """
        Bundle describing where a :class:`GoogleCloudProvisioner` operates.

        Holds the GCP project, default region, default zone, and a list of
        default tags applied (as labels) to every resource the venue creates.
    """

    def __init__(self, *, project: str, region: str, zone: str,
                 default_tags: Optional[Dict[str, str]] = None) -> None:
        """
            Construct a GcpRegionConfig.

            :param project: GCP project id (apex container).
            :param region: GCP region (e.g. ``us-central1``).
            :param zone: Default zone within the region (e.g. ``us-central1-a``).
            :param default_tags: Optional flat dict of tag key/value pairs to
                                 apply (as labels) to every created resource.

            :raises: ValueError
        """
        if project is None or len(project) == 0:
            raise ValueError("GcpRegionConfig.project must not be empty.")

        if region is None or len(region) == 0:
            raise ValueError("GcpRegionConfig.region must not be empty.")

        if zone is None or len(zone) == 0:
            raise ValueError("GcpRegionConfig.zone must not be empty.")

        effective_tags = default_tags if default_tags is not None else {}

        self._project: str = project
        self._region: str = region
        self._zone: str = zone
        self._default_tags: Dict[str, str] = effective_tags
        return

    @property
    def project(self) -> str:
        """
            Return the GCP project id.

            :returns: The project id string.
        """
        rtnval = self._project
        return rtnval

    @property
    def region(self) -> str:
        """
            Return the GCP region.

            :returns: The region string.
        """
        rtnval = self._region
        return rtnval

    @property
    def zone(self) -> str:
        """
            Return the default zone.

            :returns: The zone string.
        """
        rtnval = self._zone
        return rtnval

    @property
    def default_tags(self) -> Dict[str, str]:
        """
            Return the list of default tag dicts.

            :returns: A defensive copy of the default tag list.
        """
        rtnval = dict(self._default_tags)
        return rtnval

    def zone_supports_compact_placement(self, *, zone: str) -> bool:
        """
            Return True when the zone can host compact-placement A3 families.

            :param zone: Zone identifier to test.

            :returns: True when compact placement is supported in the zone.
        """
        rtnval = zone in _A3_COMPACT_ZONES
        return rtnval
