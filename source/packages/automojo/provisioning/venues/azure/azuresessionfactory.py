"""
    .. module:: azuresessionfactory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: AzureSessionFactory — lazy builder for azure-mgmt-* clients.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Any, Optional

from automojo.credentials.azuremanagedidentitycredential import (
    AzureManagedIdentityCredential
)
from automojo.credentials.azureserviceprincipalcredential import (
    AzureServicePrincipalCredential
)
from automojo.provisioning.venues.azure.azureerrors import AzureValidationError
from automojo.provisioning.venues.azure.azureregionconfig import (
    AzureRegionConfig
)


class AzureSessionFactory:
    """
        Lazy factory that builds ``azure-mgmt-*`` management clients from an
        Azure credential and an :class:`AzureRegionConfig`.

        The :class:`azure.identity` ``TokenCredential`` is constructed on
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
            Return the cached ``azure.identity`` token credential.

            Builds a ``ClientSecretCredential`` from a service-principal
            credential, or a ``ManagedIdentityCredential`` from a managed
            identity credential.

            :returns: An ``azure.identity`` token credential.
            :raises: AzureValidationError
        """
        if self._token_credential is not None:
            rtnval = self._token_credential
            return rtnval

        if isinstance(self._credential, AzureServicePrincipalCredential):
            from azure.identity import ClientSecretCredential
            built = ClientSecretCredential(
                tenant_id=self._credential.tenant_id,
                client_id=self._credential.client_id,
                client_secret=self._credential.client_secret,
            )
            self._token_credential = built
            rtnval = self._token_credential
            return rtnval

        if isinstance(self._credential, AzureManagedIdentityCredential):
            from azure.identity import ManagedIdentityCredential
            if self._credential.client_id is not None:
                built = ManagedIdentityCredential(
                    client_id=self._credential.client_id
                )
            else:
                built = ManagedIdentityCredential()
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

    def override_clients(self, *, resource: Optional[Any] = None,
                         network: Optional[Any] = None,
                         compute: Optional[Any] = None,
                         storage: Optional[Any] = None,
                         dns: Optional[Any] = None) -> None:
        """
            Inject pre-built (mock) management clients.

            Used by tests so the venue can be exercised without the
            ``azure.identity`` token path or real Azure calls.

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

        from azure.mgmt.resource import ResourceManagementClient
        built = ResourceManagementClient(
            credential=self.token_credential(),
            subscription_id=self._region_config.subscription_id,
        )
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

        from azure.mgmt.network import NetworkManagementClient
        built = NetworkManagementClient(
            credential=self.token_credential(),
            subscription_id=self._region_config.subscription_id,
        )
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

        from azure.mgmt.compute import ComputeManagementClient
        built = ComputeManagementClient(
            credential=self.token_credential(),
            subscription_id=self._region_config.subscription_id,
        )
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

        from azure.mgmt.storage import StorageManagementClient
        built = StorageManagementClient(
            credential=self.token_credential(),
            subscription_id=self._region_config.subscription_id,
        )
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

        from azure.mgmt.dns import DnsManagementClient
        built = DnsManagementClient(
            credential=self.token_credential(),
            subscription_id=self._region_config.subscription_id,
        )
        self._dns_client = built
        rtnval = self._dns_client
        return rtnval
