"""
    .. module:: linodeclientfactory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: LinodeClientFactory — lazy ``linode_api4`` client builder.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Optional

from ccai.credentials.linodeapitokencredential import (
    LinodeApiTokenCredential
)


class LinodeClientFactory:
    """
        Lazy factory that builds a ``linode_api4.LinodeClient`` from a
        :class:`LinodeApiTokenCredential`.

        The SDK is imported on first ``client()`` call so test processes can
        construct the factory without ``linode_api4`` installed and inject a
        mock client via :meth:`set_client`.
    """

    def __init__(self, *, credential: LinodeApiTokenCredential) -> None:
        """
            Construct a LinodeClientFactory.

            :param credential: A LinodeApiTokenCredential.
        """
        self._credential: LinodeApiTokenCredential = credential
        self._client: Optional[Any] = None
        return

    def set_client(self, *, client: Any) -> None:
        """
            Inject a pre-built (or mock) client, bypassing SDK construction.

            :param client: A ``linode_api4.LinodeClient``-compatible object.
        """
        self._client = client
        return

    def client(self) -> Any:
        """
            Return the cached client, building it on first call.

            :returns: A ``linode_api4.LinodeClient`` instance.
        """
        if self._client is not None:
            rtnval = self._client
            return rtnval

        from linode_api4 import LinodeClient
        built = LinodeClient(self._credential.token)
        self._client = built

        rtnval = self._client
        return rtnval
