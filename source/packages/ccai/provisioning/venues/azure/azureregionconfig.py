"""
    .. module:: azureregionconfig
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: AzureRegionConfig — location + subscription + default tags bundle.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Dict, Optional


class AzureRegionConfig:
    """
        Bundle describing where an :class:`AzureCloudProvisioner` operates.

        Holds the Azure subscription id, the Azure location (region), the
        name of the apex ResourceGroup for the run, and a list of default
        tags applied to every resource the venue creates.
    """

    def __init__(self, *, subscription_id: str, location: str,
                 resource_group: str,
                 default_tags: Optional[Dict[str, str]] = None) -> None:
        """
            Construct an AzureRegionConfig.

            :param subscription_id: Azure subscription id.
            :param location: Azure location / region (e.g. ``eastus``).
            :param resource_group: Apex ResourceGroup name for the run.
            :param default_tags: Optional flat dict of tag key/value pairs to
                                 apply to every created resource.

            :raises: ValueError
        """
        if subscription_id is None or len(subscription_id) == 0:
            raise ValueError(
                "AzureRegionConfig.subscription_id must not be empty."
            )

        if location is None or len(location) == 0:
            raise ValueError("AzureRegionConfig.location must not be empty.")

        if resource_group is None or len(resource_group) == 0:
            raise ValueError(
                "AzureRegionConfig.resource_group must not be empty."
            )

        effective_tags = default_tags if default_tags is not None else {}

        self._subscription_id: str = subscription_id
        self._location: str = location
        self._resource_group: str = resource_group
        self._default_tags: Dict[str, str] = effective_tags
        return

    @property
    def subscription_id(self) -> str:
        """
            Return the Azure subscription id.

            :returns: The subscription id string.
        """
        rtnval = self._subscription_id
        return rtnval

    @property
    def location(self) -> str:
        """
            Return the Azure location / region.

            :returns: The location string.
        """
        rtnval = self._location
        return rtnval

    @property
    def resource_group(self) -> str:
        """
            Return the apex ResourceGroup name.

            :returns: The resource group name.
        """
        rtnval = self._resource_group
        return rtnval

    @property
    def default_tags(self) -> Dict[str, str]:
        """
            Return the list of default tag dicts.

            :returns: A defensive copy of the default tag list.
        """
        rtnval = dict(self._default_tags)
        return rtnval
