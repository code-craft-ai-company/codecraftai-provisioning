"""
    .. module:: azuresessionfactory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: AzureSessionFactory — lazy builder for the ARM
               management clients.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Any, Optional

from ccai.credentials.azuremanagedidentitycredential import (
    AzureManagedIdentityCredential
)
from ccai.credentials.azureserviceprincipalcredential import (
    AzureServicePrincipalCredential
)
from ccai.provisioning.venues.azure.azureerrors import AzureValidationError
from ccai.restclient.azure.azurearmclient import AzureArmClient
from ccai.restclient.azure.azuretokenprovider import (
    AzureTokenProvider
)
from ccai.restclient.azure.managementclients import (
    ComputeManagementClient, DnsManagementClient,
    NetworkManagementClient, ResourceManagementClient,
    StorageManagementClient
)
from ccai.provisioning.venues.azure.azureregionconfig import (
    AzureRegionConfig
)


class AzureSessionFactory:
    """
        Lazy factory that builds the ARM management clients from an
        Azure credential and an :class:`AzureRegionConfig`.

        The token provider is constructed on
        first access and cached; each per-service client is likewise built
        once and cached.  No SDK state is created at construction time so
        this class is safe to instantiate in tests that inject mock clients
        via :meth:`override_clients`.
    """

    def __init__(self, *, credential: Any,
                 region_config: AzureRegionConfig) -> None:
        """
            Construct an AzureSessionFactory.

            :param credential: An AzureServicePrincipalCredential or an
                               AzureManagedIdentityCredential.
            :param region_config: The AzureRegionConfig.
        """
        self._credential: Any = credential
        self._region_config: AzureRegionConfig = region_config
        self._token_credential: Optional[Any] = None
        self._arm_client: Optional[Any] = None
        self._resource_client: Optional[Any] = None
        self._network_client: Optional[Any] = None
        self._compute_client: Optional[Any] = None
        self._storage_client: Optional[Any] = None
        self._dns_client: Optional[Any] = None
        return

    @property
    def region_config(self) -> AzureRegionConfig:
        """
            Return the bound :class:`AzureRegionConfig`.

            :returns: The AzureRegionConfig.
        """
        rtnval = self._region_config
        return rtnval

    def token_credential(self) -> Any:
        """
            Return the cached token provider.

            Builds a ``ClientSecretCredential`` from a service-principal
            credential, or a ``ManagedIdentityCredential`` from a managed
            identity credential.

            :returns: An :class:`AzureTokenProvider`.
            :raises: AzureValidationError
        """
        if self._token_credential is not None:
            rtnval = self._token_credential
            return rtnval

        if isinstance(self._credential, AzureServicePrincipalCredential):
            built = AzureTokenProvider(
                tenant_id=self._credential.tenant_id,
                client_id=self._credential.client_id,
                client_secret=self._credential.client_secret,
            )
            self._token_credential = built
            rtnval = self._token_credential
            return rtnval

        if isinstance(self._credential, AzureManagedIdentityCredential):
            built = AzureTokenProvider(
                use_managed_identity=True,
                client_id=self._credential.client_id,
            )
            self._token_credential = built
            rtnval = self._token_credential
            return rtnval

        err_msg_lines = [
            "AzureSessionFactory requires an AzureServicePrincipalCredential "
            "or an AzureManagedIdentityCredential."
        ]
        err_msg_lines.append("ACTUAL: {}".format(type(self._credential).__name__))
        err_msg = os.linesep.join(err_msg_lines)
        raise AzureValidationError(err_msg)

    def arm_client(self) -> Any:
        """
            Return the cached ARM transport, building it on first use.

            All five management clients share one transport, because ARM is a
            single API.

            :returns: An :class:`AzureArmClient`.
        """
        if self._arm_client is not None:
            rtnval = self._arm_client
            return rtnval

        built = AzureArmClient(
            subscription_id=self._region_config.subscription_id,
            token_provider=self.token_credential(),
        )
        self._arm_client = built
        rtnval = self._arm_client
        return rtnval

    def override_clients(self, *, resource: Optional[Any] = None,
                         network: Optional[Any] = None,
                         compute: Optional[Any] = None,
                         storage: Optional[Any] = None,
                         dns: Optional[Any] = None) -> None:
        """
            Inject pre-built (mock) management clients.

            Used by tests so the venue can be exercised without the
            token-acquisition path or real Azure calls.

            :param resource: ResourceManagementClient (or mock).
            :param network: NetworkManagementClient (or mock).
            :param compute: ComputeManagementClient (or mock).
            :param storage: StorageManagementClient (or mock).
            :param dns: DnsManagementClient (or mock).
        """
        if resource is not None:
            self._resource_client = resource
        if network is not None:
            self._network_client = network
        if compute is not None:
            self._compute_client = compute
        if storage is not None:
            self._storage_client = storage
        if dns is not None:
            self._dns_client = dns
        return

    def resource_client(self) -> Any:
        """
            Return the cached ``ResourceManagementClient``.

            :returns: A ResourceManagementClient.
        """
        if self._resource_client is not None:
            rtnval = self._resource_client
            return rtnval

        built = ResourceManagementClient(arm_client=self.arm_client())
        self._resource_client = built
        rtnval = self._resource_client
        return rtnval

    def network_client(self) -> Any:
        """
            Return the cached ``NetworkManagementClient``.

            :returns: A NetworkManagementClient.
        """
        if self._network_client is not None:
            rtnval = self._network_client
            return rtnval

        built = NetworkManagementClient(arm_client=self.arm_client())
        self._network_client = built
        rtnval = self._network_client
        return rtnval

    def compute_client(self) -> Any:
        """
            Return the cached ``ComputeManagementClient``.

            :returns: A ComputeManagementClient.
        """
        if self._compute_client is not None:
            rtnval = self._compute_client
            return rtnval

        built = ComputeManagementClient(arm_client=self.arm_client())
        self._compute_client = built
        rtnval = self._compute_client
        return rtnval

    def storage_client(self) -> Any:
        """
            Return the cached ``StorageManagementClient``.

            :returns: A StorageManagementClient.
        """
        if self._storage_client is not None:
            rtnval = self._storage_client
            return rtnval

        built = StorageManagementClient(arm_client=self.arm_client())
        self._storage_client = built
        rtnval = self._storage_client
        return rtnval

    def dns_client(self) -> Any:
        """
            Return the cached ``DnsManagementClient``.

            :returns: A DnsManagementClient.
        """
        if self._dns_client is not None:
            rtnval = self._dns_client
            return rtnval

        built = DnsManagementClient(arm_client=self.arm_client())
        self._dns_client = built
        rtnval = self._dns_client
        return rtnval
