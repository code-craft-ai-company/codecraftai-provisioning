"""
    .. module:: awsboto3sessionfactory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: AwsBoto3SessionFactory — lazy signed-transport builder.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Optional

import os

from ccai.credentials.awsaccesskeycredential import AwsAccessKeyCredential
from ccai.provisioning.venues.aws.awsregionconfig import AwsRegionConfig
from ccai.restclient.aws.awstransport import AwsTransport
from ccai.restclient.aws.serviceclients import build_clients


class AwsBoto3SessionFactory:
    """
        Lazy factory that builds a signed AWS transport from an
        :class:`AwsAccessKeyCredential` and an :class:`AwsRegionConfig`.

        The session is constructed on first access and cached.  No global
        boto3 state is created at construction time, so this class is safe
        to instantiate in tests that inject fake service clients via the
        process.
    """

    def __init__(self, *, credential: AwsAccessKeyCredential,
                 region_config: AwsRegionConfig) -> None:
        """
            Construct an AwsBoto3SessionFactory.

            :param credential: An AwsAccessKeyCredential.
            :param region_config: The AwsRegionConfig.
        """
        self._credential: AwsAccessKeyCredential = credential
        self._region_config: AwsRegionConfig = region_config
        self._session: Optional[Any] = None
        self._clients: dict = {}
        return

    @property
    def region_config(self) -> AwsRegionConfig:
        """
            Return the bound :class:`AwsRegionConfig`.

            :returns: The AwsRegionConfig.
        """
        rtnval = self._region_config
        return rtnval

    def transport(self) -> Any:
        """
            Return the cached signed transport, building it on first use.

            :returns: An :class:`AwsTransport`.
        """
        if self._session is not None:
            rtnval = self._session
            return rtnval

        built = AwsTransport(
            access_key=self._credential.keyid,
            secret_key=self._credential.secret,
            region=self._region_config.region,
        )
        self._session = built

        rtnval = self._session
        return rtnval

    def client(self, *, service_name: str) -> Any:
        """
            Return a service client, building it on first use.

            :param service_name: AWS service identifier (``ec2``, ``s3``,
                ``route53``, ``ssm``, ``fsx``).

            :returns: The service client.

            :raises: ValueError when the service is not supported.
        """
        cached = self._clients.get(service_name, None)
        if cached is not None:
            rtnval = cached
            return rtnval

        clients = build_clients(transport=self.transport())

        if service_name not in clients:
            err_msg_lines = ["Unknown AWS service requested."]
            err_msg_lines.append("REQUESTED: {!r}".format(service_name))
            err_msg_lines.append("KNOWN: {}".format(
                ", ".join(sorted(clients.keys()))))
            err_msg = os.linesep.join(err_msg_lines)
            raise ValueError(err_msg)

        built = clients[service_name]
        self._clients[service_name] = built

        rtnval = built
        return rtnval

    def register_client(self, *, service_name: str, client: Any) -> None:
        """
            Inject a pre-built client for a service name.

            :param service_name: The service identifier.
            :param client: The client object to use.
        """
        self._clients[service_name] = client
        return
