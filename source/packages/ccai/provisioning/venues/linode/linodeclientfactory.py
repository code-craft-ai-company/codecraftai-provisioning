"""
    .. module:: linodeclientfactory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: LinodeClientFactory — lazy Linode REST client builder.

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
        Lazy factory that builds a
        :class:`ccai.restclient.linode.linoderestclient.LinodeRestClient`
        from a :class:`LinodeApiTokenCredential`.

        The client is built on first ``client()`` call, so tests can
        construct the factory and inject a fake via :meth:`set_client`
        without any network access.
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

            :param client: A :class:`LinodeRestClient`-compatible object.
        """
        self._client = client
        return

    def client(self) -> Any:
        """
            Return the cached client, building it on first call.

            :returns: A :class:`LinodeRestClient` instance.
        """
        if self._client is not None:
            rtnval = self._client
            return rtnval

        from ccai.restclient.linode.linoderestclient import (
            LinodeRestClient
        )
        built = LinodeRestClient(token=self._credential.token)
        self._client = built

        rtnval = self._client
        return rtnval
