"""
    .. module:: ocisessionfactory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: OciSessionFactory — lazy builder of the ``oci`` SDK config and
               service clients from an OracleCloudApiKeyCredential.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, Optional

from automojo.credentials.oraclecloudapikeycredential import (
    OracleCloudApiKeyCredential
)
from automojo.provisioning.venues.oracle.ociregionconfig import OciRegionConfig


class OciSessionFactory:
    """
        Lazy factory that builds the ``oci`` SDK config dict and per-service
        clients from an :class:`OracleCloudApiKeyCredential` and an
        :class:`OciRegionConfig`.

        The OCI SDK takes a plain ``config`` dict (no global session state)
        plus an in-memory signer built from the API signing key.  Clients are
        constructed on first access and cached.  No SDK calls happen at
        construction time, so this class is safe to instantiate in tests that
        swap the ``oci`` clients for mocks.
    """

    def __init__(self, *, credential: OracleCloudApiKeyCredential,
                 region_config: OciRegionConfig) -> None:
        """
            Construct an OciSessionFactory.

            :param credential: An OracleCloudApiKeyCredential.
            :param region_config: The OciRegionConfig.
        """
        self._credential: OracleCloudApiKeyCredential = credential
        self._region_config: OciRegionConfig = region_config
        self._config: Optional[Dict[str, Any]] = None
        self._clients: Dict[str, Any] = {}
        return

    @property
    def region_config(self) -> OciRegionConfig:
        """
            Return the bound :class:`OciRegionConfig`.

            :returns: The OciRegionConfig.
        """
        rtnval = self._region_config
        return rtnval

    def config(self) -> Dict[str, Any]:
        """
            Return the cached ``oci`` SDK config dict, building it on first
            call.

            :returns: An ``oci`` SDK config dict.
        """
        if self._config is not None:
            rtnval = self._config
            return rtnval

        built: Dict[str, Any] = {}
        built["tenancy"] = self._credential.tenancy_ocid
        built["user"] = self._credential.user_ocid
        built["fingerprint"] = self._credential.fingerprint
        built["key_content"] = self._credential.private_key
        built["region"] = self._region_config.region
        if self._credential.passphrase is not None:
            built["pass_phrase"] = self._credential.passphrase
        self._config = built

        rtnval = self._config
        return rtnval

    def client(self, *, service_name: str) -> Any:
        """
            Return an ``oci`` SDK service client, building it on first call.

            Supported service names map to ``oci`` SDK client classes:

            - ``virtual_network`` → ``oci.core.VirtualNetworkClient``
            - ``compute``         → ``oci.core.ComputeClient``
            - ``compute_management`` → ``oci.core.ComputeManagementClient``
            - ``blockstorage``    → ``oci.core.BlockstorageClient``
            - ``object_storage``  → ``oci.object_storage.ObjectStorageClient``
            - ``dns``             → ``oci.dns.DnsClient``
            - ``file_storage``    → ``oci.file_storage.FileStorageClient``

            :param service_name: A supported service identifier.

            :returns: An ``oci`` SDK service client.
            :raises: ValueError
        """
        if service_name in self._clients:
            rtnval = self._clients[service_name]
            return rtnval

        import oci

        config = self.config()
        if service_name == "virtual_network":
            built = oci.core.VirtualNetworkClient(config)
        elif service_name == "compute":
            built = oci.core.ComputeClient(config)
        elif service_name == "compute_management":
            built = oci.core.ComputeManagementClient(config)
        elif service_name == "blockstorage":
            built = oci.core.BlockstorageClient(config)
        elif service_name == "object_storage":
            built = oci.object_storage.ObjectStorageClient(config)
        elif service_name == "dns":
            built = oci.dns.DnsClient(config)
        elif service_name == "file_storage":
            built = oci.file_storage.FileStorageClient(config)
        else:
            raise ValueError(
                "OciSessionFactory: unknown service_name {!r}".format(
                    service_name
                )
            )

        self._clients[service_name] = built
        rtnval = built
        return rtnval

    def register_client(self, *, service_name: str, client: Any) -> None:
        """
            Inject a pre-built client for a service name.

            Intended for tests that supply ``unittest.mock`` stand-ins for
            the ``oci`` SDK clients.

            :param service_name: The service identifier.
            :param client: The client object to use for that service.
        """
        self._clients[service_name] = client
        return
