"""
    .. module:: awsregionconfig
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: AwsRegionConfig — region + AZ + default tags bundle.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Dict, Optional


class AwsRegionConfig:
    """
        Bundle describing where an :class:`AwsCloudProvisioner` operates.

        Holds the AWS region, default availability zone, and a list of
        default tags that are applied to every resource the venue creates.
    """

    def __init__(self, *, region: str, availability_zone: str,
                 default_tags: Optional[Dict[str, str]] = None) -> None:
        """
            Construct an AwsRegionConfig.

            :param region: AWS region (e.g. ``us-east-1``).
            :param availability_zone: AZ within the region (e.g. ``us-east-1a``).
            :param default_tags: Optional flat dict of tag key/value pairs to
                                 apply to every created resource.
        """
        if region is None or len(region) == 0:
            raise ValueError("AwsRegionConfig.region must not be empty.")

        if availability_zone is None or len(availability_zone) == 0:
            raise ValueError(
                "AwsRegionConfig.availability_zone must not be empty."
            )

        effective_tags = default_tags if default_tags is not None else {}

        self._region: str = region
        self._availability_zone: str = availability_zone
        self._default_tags: Dict[str, str] = effective_tags
        return

    @property
    def region(self) -> str:
        """
            Return the AWS region.

            :returns: The region string.
        """
        rtnval = self._region
        return rtnval

    @property
    def availability_zone(self) -> str:
        """
            Return the default availability zone.

            :returns: The AZ string.
        """
        rtnval = self._availability_zone
        return rtnval

    @property
    def default_tags(self) -> Dict[str, str]:
        """
            Return the list of default tag dicts.

            :returns: A defensive copy of the default tag list.
        """
        rtnval = dict(self._default_tags)
        return rtnval
