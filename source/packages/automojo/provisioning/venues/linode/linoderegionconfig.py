"""
    .. module:: linoderegionconfig
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: LinodeRegionConfig — region + object-storage cluster + default
               tags bundle.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Dict, Optional


class LinodeRegionConfig:
    """
        Bundle describing where a :class:`LinodeCloudProvisioner` operates.

        Holds the Linode region slug, the default object-storage cluster, and
        a list of default tags applied to every created resource.
    """

    def __init__(self, *, region: str,
                 object_storage_cluster: str,
                 default_tags: Optional[Dict[str, str]] = None) -> None:
        """
            Construct a LinodeRegionConfig.

            :param region: Linode region slug (e.g. ``us-east``).
            :param object_storage_cluster: Object-storage cluster identifier
                                           (e.g. ``us-east-1``).
            :param default_tags: Optional flat dict of tag key/value pairs to
                                 apply to every created resource.
        """
        if region is None or len(region) == 0:
            raise ValueError("LinodeRegionConfig.region must not be empty.")

        if object_storage_cluster is None or len(object_storage_cluster) == 0:
            raise ValueError(
                "LinodeRegionConfig.object_storage_cluster must not be empty."
            )

        effective_tags = default_tags if default_tags is not None else {}

        self._region: str = region
        self._object_storage_cluster: str = object_storage_cluster
        self._default_tags: Dict[str, str] = effective_tags
        return

    @property
    def region(self) -> str:
        """
            Return the Linode region slug.

            :returns: The region string.
        """
        rtnval = self._region
        return rtnval

    @property
    def object_storage_cluster(self) -> str:
        """
            Return the default object-storage cluster identifier.

            :returns: The cluster string.
        """
        rtnval = self._object_storage_cluster
        return rtnval

    @property
    def default_tags(self) -> Dict[str, str]:
        """
            Return the list of default tag dicts.

            :returns: A defensive copy of the default tag list.
        """
        rtnval = dict(self._default_tags)
        return rtnval
