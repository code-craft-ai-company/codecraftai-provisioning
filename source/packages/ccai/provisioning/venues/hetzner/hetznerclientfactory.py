"""
    .. module:: hetznerclientfactory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Lazy factory producing a Hetzner Cloud REST client for the
               Hetzner venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Optional

from ccai.credentials.hetznerapitokencredential import (
    HetznerApiTokenCredential
)
from ccai.restclient.hetzner.hetznerrestclient import HetznerRestClient


class HetznerClientFactory:
    """
        Lazy factory that builds and caches a :class:`HetznerRestClient`.

        Construction is deferred to first use so the venue module stays
        importable without a credential being exercised.  Tests inject a
        pre-built mock client via the ``client`` constructor argument.
    """

    def __init__(self, *, credential: HetznerApiTokenCredential,
                 client: Optional[Any] = None) -> None:
        """
            Construct a HetznerClientFactory.

            :param credential: HetznerApiTokenCredential carrying the token.
            :param client: Optional pre-built client (used by unit tests to
                           inject a mock).
        """
        self._credential: HetznerApiTokenCredential = credential
        self._client: Optional[Any] = client
        return

    def client(self) -> Any:
        """
            Return the Hetzner client, constructing it on first use.

            :returns: A :class:`HetznerRestClient` (or injected mock).
        """
        if self._client is not None:
            rtnval = self._client
            return rtnval

        built = HetznerRestClient(token=self._credential.token)
        self._client = built
        rtnval = built
        return rtnval
