"""
    .. module:: doclient
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: DigitalOceanClient — thin lazily-constructed wrapper over the
               ``pydo`` SDK.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Any, Dict, Optional, Tuple

from ccai.errors.exceptions import ConfigurationError
from ccai.credentials.digitaloceanapitokencredential import (
    DigitalOceanApiTokenCredential
)


class DigitalOceanClient:
    """
        Thin wrapper around the ``pydo`` SDK client.

        The ``pydo`` SDK is imported lazily on first use so that the venue
        package imports cleanly in environments where ``pydo`` is not
        installed; tests inject a mock ``pydo`` client directly via the
        ``raw_client`` constructor argument and never touch the network.

        The resource-collection attributes (``vpcs``, ``firewalls``,
        ``droplets``, ``volumes``, ``ssh_keys``, ``domains``, ``tags``,
        ``actions``) mirror the ``pydo`` client surface.
    """

    def __init__(self, *, credential: DigitalOceanApiTokenCredential,
                 raw_client: Optional[Any] = None,
                 spaces_client: Optional[Any] = None) -> None:
        """
            Construct a DigitalOceanClient.

            :param credential: DigitalOceanApiTokenCredential carrying the
                               personal-access-token.
            :param raw_client: Optional pre-built ``pydo`` client (or mock).
                               When omitted the ``pydo`` SDK is imported and
                               a client is built lazily on first access.
            :param spaces_client: Optional pre-built S3-compatible client (or
                                  mock) for Spaces.  When omitted a boto3 S3
                                  client is built lazily per region.
        """
        self._credential: DigitalOceanApiTokenCredential = credential
        self._raw_client: Optional[Any] = raw_client
        self._spaces_client: Optional[Any] = spaces_client
        self._spaces_clients_by_region: Dict[str, Any] = {}
        return

    def _build_raw_client(self) -> Any:
        """
            Lazily import ``pydo`` and build a real client.

            :returns: A ``pydo.Client`` instance.
            :raises: RuntimeError
        """
        try:
            import pydo
        except ImportError as xcpt:
            err_msg_lines = ["The 'pydo' SDK is required for live "
                             "DigitalOcean calls."]
            err_msg_lines.append("INSTALL: python -m pip install pydo")
            err_msg_lines.append("CAUSE: {}".format(xcpt))
            err_msg = os.linesep.join(err_msg_lines)
            raise RuntimeError(err_msg) from None

        built = pydo.Client(token=self._credential.token)
        rtnval = built
        return rtnval

    def raw(self) -> Any:
        """
            Return the underlying ``pydo`` client, building it if needed.

            :returns: The raw ``pydo`` client (or injected mock).
        """
        if self._raw_client is None:
            self._raw_client = self._build_raw_client()
        rtnval = self._raw_client
        return rtnval

    @property
    def vpcs(self) -> Any:
        """
            Return the ``pydo`` vpcs resource collection.

            :returns: The vpcs collection.
        """
        rtnval = self.raw().vpcs
        return rtnval

    @property
    def firewalls(self) -> Any:
        """
            Return the ``pydo`` firewalls resource collection.

            :returns: The firewalls collection.
        """
        rtnval = self.raw().firewalls
        return rtnval

    @property
    def droplets(self) -> Any:
        """
            Return the ``pydo`` droplets resource collection.

            :returns: The droplets collection.
        """
        rtnval = self.raw().droplets
        return rtnval

    @property
    def volumes(self) -> Any:
        """
            Return the ``pydo`` volumes resource collection.

            :returns: The volumes collection.
        """
        rtnval = self.raw().volumes
        return rtnval

    @property
    def volume_actions(self) -> Any:
        """
            Return the ``pydo`` volume_actions resource collection.

            :returns: The volume_actions collection.
        """
        rtnval = self.raw().volume_actions
        return rtnval

    @property
    def ssh_keys(self) -> Any:
        """
            Return the ``pydo`` ssh_keys resource collection.

            :returns: The ssh_keys collection.
        """
        rtnval = self.raw().ssh_keys
        return rtnval

    @property
    def domains(self) -> Any:
        """
            Return the ``pydo`` domains resource collection.

            :returns: The domains collection.
        """
        rtnval = self.raw().domains
        return rtnval

    def _resolve_spaces_credentials(self) -> Tuple[str, str]:
        """
            Resolve the S3-compatible Spaces access key and secret.

            Spaces keys are distinct from the DigitalOcean API token.  They
            are taken from the credential (``spaces_access_key`` /
            ``spaces_secret_key``) when present, else from the
            ``DIGITALOCEAN_SPACES_KEY`` / ``DIGITALOCEAN_SPACES_SECRET``
            environment variables.

            :returns: A ``(access_key, secret_key)`` tuple.
            :raises: ConfigurationError when either value is unavailable.
        """
        access_key = getattr(self._credential, "spaces_access_key", None)
        if access_key is None or len(access_key) == 0:
            access_key = os.environ.get("DIGITALOCEAN_SPACES_KEY", None)

        secret_key = getattr(self._credential, "spaces_secret_key", None)
        if secret_key is None or len(secret_key) == 0:
            secret_key = os.environ.get("DIGITALOCEAN_SPACES_SECRET", None)

        access_missing = access_key is None or len(access_key) == 0
        secret_missing = secret_key is None or len(secret_key) == 0
        if access_missing or secret_missing:
            err_msg_lines = [
                "DigitalOcean Spaces bucket operations require S3-compatible "
                "Spaces access keys, which are distinct from the API token."
            ]
            err_msg_lines.append(
                "Set the credential's spaces_access_key / spaces_secret_key, "
                "or the DIGITALOCEAN_SPACES_KEY / DIGITALOCEAN_SPACES_SECRET "
                "environment variables."
            )
            err_msg = os.linesep.join(err_msg_lines)
            raise ConfigurationError(err_msg)

        rtnval = (access_key, secret_key)
        return rtnval

    def spaces(self, *, region: str) -> Any:
        """
            Return an S3-compatible client for DigitalOcean Spaces in a region.

            The DigitalOcean REST API (pydo) cannot manage Spaces buckets, so
            bucket lifecycle goes through boto3 against the regional Spaces
            endpoint using Spaces access keys.  A pre-built client injected via
            the constructor (for tests) is returned as-is.

            :param region: The Spaces region slug (e.g. ``nyc3``).

            :returns: A boto3 S3 client bound to the regional Spaces endpoint.
            :raises: ConfigurationError when Spaces credentials are unavailable.
        """
        if self._spaces_client is not None:
            rtnval = self._spaces_client
            return rtnval

        cached = self._spaces_clients_by_region.get(region, None)
        if cached is not None:
            rtnval = cached
            return rtnval

        access_key, secret_key = self._resolve_spaces_credentials()

        import boto3
        session = boto3.session.Session()
        endpoint_url = "https://{}.digitaloceanspaces.com".format(region)
        built = session.client(
            "s3", region_name=region, endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        self._spaces_clients_by_region[region] = built
        rtnval = built
        return rtnval
