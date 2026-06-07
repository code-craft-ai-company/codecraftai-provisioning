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

from typing import Any, Optional

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
                 raw_client: Optional[Any] = None) -> None:
        """
            Construct a DigitalOceanClient.

            :param credential: DigitalOceanApiTokenCredential carrying the
                               personal-access-token.
            :param raw_client: Optional pre-built ``pydo`` client (or mock).
                               When omitted the ``pydo`` SDK is imported and
                               a client is built lazily on first access.
        """
        self._credential: DigitalOceanApiTokenCredential = credential
        self._raw_client: Optional[Any] = raw_client
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

    @property
    def spaces(self) -> Any:
        """
            Return the Spaces (S3-compatible) resource collection.

            :returns: The spaces collection.
        """
        rtnval = self.raw().spaces
        return rtnval
