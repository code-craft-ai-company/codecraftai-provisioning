
__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Automation Mojo LLC"
__credits__ = []

from typing import Dict, Optional


class CloudVenue:
    """
        CloudVenue class to represent a cloud venue for resource provisioning.
    """

    def __init__(self, *, name: str, provider: str, region: str, credential: str,
                 account: Optional[str] = None, endpoint: Optional[str] = None,
                 settings: Optional[Dict[str, str]] = None):
        """
            Initialize the CloudVenue with neutral provider-agnostic fields.

            :param name: User's label for this venue instance.
            :param provider: Provider discriminator (aws, azure, vsphere, ...).
            :param region: Neutral location term for the venue.
            :param credential: Credential reference used when provisioning.
            :param account: Optional neutral account-scope term (Azure
                            subscription-id, GCP project-id, Oracle tenancy-ocid).
            :param endpoint: Optional neutral management-endpoint URL.
            :param settings: Optional mapping of venue-native config keys.
        """
        self._name = name
        self._provider = provider
        self._region = region
        self._credential = credential
        self._account = account
        self._endpoint = endpoint

        if settings is None:
            self._settings = {}
        else:
            self._settings = settings

        return

    @property
    def account(self) -> Optional[str]:
        """
            Get the neutral account-scope term of the cloud venue.

            :returns: The account-scope term, or None when the venue has no
                      such concept.
        """
        return self._account

    @property
    def credential(self) -> str:
        """
            Get the credential used when creating the cloud resource.

            :returns: The credential used when creating the cloud resource.
        """
        return self._credential

    @property
    def endpoint(self) -> Optional[str]:
        """
            Get the neutral management-endpoint URL of the cloud venue.

            :returns: The management-endpoint URL, or None for public clouds
                      with an implicit endpoint.
        """
        return self._endpoint

    @property
    def name(self) -> str:
        """
            Get the name of the cloud venue.

            :returns: The name of the cloud venue.
        """
        return self._name

    @property
    def provider(self) -> str:
        """
            Get the provider of the cloud venue.

            :returns: The provider of the cloud venue.
        """
        return self._provider

    @property
    def region(self) -> str:
        """
            Get the region of the cloud venue.

            :returns: The region of the cloud venue.
        """
        return self._region

    @property
    def settings(self) -> Dict[str, str]:
        """
            Get the venue-native settings mapping of the cloud venue.

            :returns: The mapping of venue-native config keys.
        """
        return self._settings
