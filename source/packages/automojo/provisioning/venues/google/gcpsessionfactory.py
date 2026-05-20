"""
    .. module:: gcpsessionfactory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: GcpSessionFactory — lazy google-cloud-* client builder.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Any, Dict, Optional, Union

from automojo.credentials.gcpserviceaccountkeycredential import (
    GcpServiceAccountKeyCredential
)
from automojo.credentials.gcpworkloadidentitycredential import (
    GcpWorkloadIdentityCredential
)
from automojo.provisioning.venues.google.gcpregionconfig import GcpRegionConfig
from automojo.provisioning.venues.google.gcperrors import GcpValidationError


# Service identifiers accepted by :meth:`GcpSessionFactory.client`.
SERVICE_COMPUTE = "compute"
SERVICE_TPU = "tpu"
SERVICE_STORAGE = "storage"
SERVICE_DNS = "dns"


class GcpSessionFactory:
    """
        Lazy factory that builds ``google-cloud-*`` clients from a GCP
        credential and a :class:`GcpRegionConfig`.

        Clients are constructed on first access and cached.  No global
        Google state is created at construction time, so this class is safe
        to instantiate in tests where the ``google-cloud-*`` client classes
        are swapped for ``unittest.mock`` doubles via :meth:`set_client`.
    """

    def __init__(self, *,
                 credential: Union[GcpServiceAccountKeyCredential,
                                   GcpWorkloadIdentityCredential],
                 region_config: GcpRegionConfig) -> None:
        """
            Construct a GcpSessionFactory.

            :param credential: A GCP service-account-key or workload-identity
                               credential.
            :param region_config: The GcpRegionConfig.
        """
        self._credential: Union[GcpServiceAccountKeyCredential,
                                GcpWorkloadIdentityCredential] = credential
        self._region_config: GcpRegionConfig = region_config
        self._google_credentials: Optional[Any] = None
        self._clients: Dict[str, Any] = {}
        return

    @property
    def region_config(self) -> GcpRegionConfig:
        """
            Return the bound :class:`GcpRegionConfig`.

            :returns: The GcpRegionConfig.
        """
        rtnval = self._region_config
        return rtnval

    @property
    def project(self) -> str:
        """
            Return the GCP project id this factory operates against.

            :returns: The project id string.
        """
        rtnval = self._region_config.project
        return rtnval

    def google_credentials(self) -> Any:
        """
            Return cached ``google.auth`` credentials, building on first call.

            :returns: A ``google.auth.credentials.Credentials`` instance.
        """
        if self._google_credentials is not None:
            rtnval = self._google_credentials
            return rtnval

        if isinstance(self._credential, GcpServiceAccountKeyCredential):
            from google.oauth2 import service_account
            info = {
                "type": "service_account",
                "project_id": self._credential.project_id,
                "private_key_id": self._credential.private_key_id,
                "private_key": self._credential.private_key,
                "client_email": self._credential.client_email,
                "token_uri": self._credential.token_uri,
            }
            built = service_account.Credentials.from_service_account_info(info)
            self._google_credentials = built
            rtnval = self._google_credentials
            return rtnval

        if isinstance(self._credential, GcpWorkloadIdentityCredential):
            import google.auth
            built, _ = google.auth.default()
            self._google_credentials = built
            rtnval = self._google_credentials
            return rtnval

        err_msg_lines = ["Unsupported GCP credential type for session factory."]
        err_msg_lines.append("ACTUAL: {}".format(type(self._credential).__name__))
        err_msg = os.linesep.join(err_msg_lines)
        raise GcpValidationError(err_msg)

    def set_client(self, *, service_name: str, client: Any) -> None:
        """
            Inject a pre-built (or mocked) client for a service.

            Intended for tests that supply ``unittest.mock`` doubles in place
            of live ``google-cloud-*`` clients.

            :param service_name: One of the SERVICE_* identifiers.
            :param client: The client object to cache.
        """
        self._clients[service_name] = client
        return

    def client(self, *, service_name: str) -> Any:
        """
            Return a cached google-cloud client, building it on first call.

            :param service_name: One of the SERVICE_* identifiers.

            :returns: A google-cloud client object.
            :raises: GcpValidationError
        """
        cached = self._clients.get(service_name, None)
        if cached is not None:
            rtnval = cached
            return rtnval

        creds = self.google_credentials()

        if service_name == SERVICE_COMPUTE:
            from google.cloud import compute_v1
            built: Any = {
                "networks": compute_v1.NetworksClient(credentials=creds),
                "subnetworks": compute_v1.SubnetworksClient(credentials=creds),
                "firewalls": compute_v1.FirewallsClient(credentials=creds),
                "instances": compute_v1.InstancesClient(credentials=creds),
                "disks": compute_v1.DisksClient(credentials=creds),
                "resource_policies": compute_v1.ResourcePoliciesClient(
                    credentials=creds
                ),
                "images": compute_v1.ImagesClient(credentials=creds),
            }
        elif service_name == SERVICE_TPU:
            from google.cloud import tpu_v2
            built = tpu_v2.TpuClient(credentials=creds)
        elif service_name == SERVICE_STORAGE:
            from google.cloud import storage
            built = storage.Client(project=self.project, credentials=creds)
        elif service_name == SERVICE_DNS:
            from google.cloud import dns
            built = dns.Client(project=self.project, credentials=creds)
        else:
            err_msg_lines = ["Unknown GCP service name requested."]
            err_msg_lines.append("REQUESTED: {!r}".format(service_name))
            err_msg = os.linesep.join(err_msg_lines)
            raise GcpValidationError(err_msg)

        self._clients[service_name] = built
        rtnval = built
        return rtnval
