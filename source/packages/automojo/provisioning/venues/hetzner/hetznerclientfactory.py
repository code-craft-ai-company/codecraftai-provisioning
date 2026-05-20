"""
    .. module:: hetznerclientfactory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Lazy factory producing an hcloud Client for the Hetzner venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Any, Optional

from automojo.credentials.hetznerapitokencredential import (
    HetznerApiTokenCredential
)
from automojo.provisioning.venues.hetzner.hetznererrors import (
    HetznerValidationError
)


class HetznerClientFactory:
    """
        Lazy factory that builds and caches an ``hcloud.Client``.

        The ``hcloud`` SDK is imported lazily so that the venue module can be
        imported (and unit-tested with a mocked client) on hosts where the
        SDK is not installed.  Tests inject a pre-built mock client via the
        ``client`` constructor argument.
    """

    def __init__(self, *, credential: HetznerApiTokenCredential,
                 client: Optional[Any] = None) -> None:
        """
            Construct a HetznerClientFactory.

            :param credential: HetznerApiTokenCredential carrying the token.
            :param client: Optional pre-built client (used by unit tests to
                           inject a mock; bypasses the SDK import).
        """
        self._credential: HetznerApiTokenCredential = credential
        self._client: Optional[Any] = client
        return

    def client(self) -> Any:
        """
            Return the hcloud Client, constructing it on first use.

            :returns: An ``hcloud.Client`` (or injected mock).
            :raises: HetznerValidationError
        """
        if self._client is not None:
            rtnval = self._client
            return rtnval

        try:
            from hcloud import Client as HCloudClient
        except ImportError as xcpt:
            err_msg_lines = [
                "The hcloud SDK is required to build a live Hetzner client."
            ]
            err_msg_lines.append("Install it with: python -m pip install hcloud")
            err_msg_lines.append("CAUSE: {}".format(xcpt))
            err_msg = os.linesep.join(err_msg_lines)
            raise HetznerValidationError(err_msg) from None

        built = HCloudClient(token=self._credential.token)
        self._client = built
        rtnval = built
        return rtnval
