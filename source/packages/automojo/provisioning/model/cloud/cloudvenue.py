
__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Automation Mojo LLC"
__credits__ = []


class CloudVenue:
    """
        CloudVenue class to represent a cloud venue for resource provisioning.
    """

    def __init__(self, *, name: str, provider: str, management_url: str, subscription: str, region: str, credential: str):
        """
        Initialize the CloudVenue with a name and region.

        :param name: Name of the cloud venue.
        :param region: Region of the cloud venue.
        """
        self._name = name
        self._provider = provider
        self._management_url = management_url
        self._subscription = subscription
        self._region = region
        self._credential = credential
        return
    
    @property
    def credential(self) -> str:
        """
        Get the credential used when creating the cloud resource.

        :return: The credential used when creating the cloud resource.
        """
        return self._credential
    
    @property
    def management_url(self) -> str:
        """
        Get the management URL of the cloud venue.

        :return: The management URL of the cloud venue.
        """
        return self._management_url
    
    @property
    def name(self) -> str:
        """
        Get the name of the cloud venue.

        :return: The name of the cloud venue.
        """
        return self._name
    
    @property
    def provider(self) -> str:
        """
        Get the provider of the cloud venue.

        :return: The provider of the cloud venue.
        """
        return self._provider
    
    @property
    def region(self) -> str:
        """
        Get the region of the cloud venue.

        :return: The region of the cloud venue.
        """
        return self._region
    
    @property
    def subscription(self) -> str:
        """
        Get the subscription of the cloud venue.

        :return: The subscription of the cloud venue.
        """
        return self._subscription
    



