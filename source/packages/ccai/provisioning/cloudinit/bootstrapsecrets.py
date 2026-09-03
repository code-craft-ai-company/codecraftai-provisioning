"""
    .. module:: bootstrapsecrets
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Per-run container for secrets the first-boot renderers need,
               resolved once by the engine and bound for the apply stages.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>

    Specs never carry secrets.  ``PythonEnvironmentSpec.index_credential``
    names a credential-vault entry; the engine resolves every such name
    during LOAD_VALIDATE into a :class:`BootstrapSecrets` and binds it for
    the duration of the apply stages with :func:`bind_bootstrap_secrets`.
    Renderers read :func:`current_bootstrap_secrets` when a caller does not
    hand them a container explicitly, so the twenty venue user-data paths
    need no new plumbing and no venue ever touches a credential vault.

    The binding is a :class:`contextvars.ContextVar`, which is per-thread
    and per-task, so two engines applying concurrently in one process do
    not see each other's secrets.
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import contextlib
import contextvars

from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, Optional


@dataclass(frozen=True)
class IndexCredential:
    """
        Credentials for a package index.

        :param username: HTTP basic-auth username (``__token__`` for
                         token-style indexes such as PyPI and most private
                         mirrors).
        :param secret: The password or token.
    """
    username: str
    secret: str

    def __repr__(self) -> str:
        """
            Never let the secret into a log line or an exception message.
        """
        rtnval = "IndexCredential(username={!r}, secret='***')".format(self.username)
        return rtnval


@dataclass
class BootstrapSecrets:
    """
        Resolved secrets for one provisioning run.

        :param index_credentials: Map of credential-vault reference (the
                                  value of ``PythonEnvironmentSpec.
                                  index_credential``) to the resolved
                                  :class:`IndexCredential`.
    """
    index_credentials: Dict[str, IndexCredential] = field(default_factory=dict)

    def credential_for(self, *, spec: Any) -> Optional[IndexCredential]:
        """
            Look up the credential a spec names.

            :param spec: A ``PythonEnvironmentSpec`` (anything with an
                         ``index_credential`` attribute).

            :returns: The :class:`IndexCredential`, or ``None`` when the spec
                      names no credential or the name is not resolved here.
        """
        reference = getattr(spec, "index_credential", None)
        if reference is None:
            rtnval: Optional[IndexCredential] = None
            return rtnval
        rtnval = self.index_credentials.get(reference, None)
        return rtnval

    def __repr__(self) -> str:
        rtnval = "BootstrapSecrets(index_credentials={})".format(
            sorted(self.index_credentials.keys())
        )
        return rtnval


_CURRENT: contextvars.ContextVar = contextvars.ContextVar(
    "ccai_provisioning_bootstrap_secrets", default=None
)


def current_bootstrap_secrets() -> Optional[BootstrapSecrets]:
    """
        The :class:`BootstrapSecrets` bound for the calling context, or
        ``None`` outside an engine apply.

        :returns: The bound container or ``None``.
    """
    rtnval = _CURRENT.get()
    return rtnval


@contextlib.contextmanager
def bind_bootstrap_secrets(secrets: Optional[BootstrapSecrets]) -> Iterator[None]:
    """
        Bind ``secrets`` as the current container for the duration of the
        ``with`` block, restoring the previous binding afterwards.

        :param secrets: The container to bind (``None`` clears the binding).
    """
    token = _CURRENT.set(secrets)
    try:
        yield
    finally:
        _CURRENT.reset(token)
    return


__all__ = [
    "BootstrapSecrets",
    "IndexCredential",
    "bind_bootstrap_secrets",
    "current_bootstrap_secrets",
]
