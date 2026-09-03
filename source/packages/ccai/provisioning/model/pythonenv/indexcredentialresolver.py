"""
    .. module:: indexcredentialresolver
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Validate-time resolver for PythonEnvironmentSpec index credentials.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Any, Callable, Iterable

from ccai.credentials.apitokencredential import ApiTokenCredential
from ccai.credentials.basiccredential import BasicCredential
from ccai.credentials.personalapitokencredential import PersonalApiTokenCredential
from ccai.credentials.secrettokencredential import SecretTokenCredential
from ccai.errors.exceptions import ConfigurationError
from ccai.interfaces.pythonenvspec import PythonEnvironmentSpec
from ccai.interfaces.schemasemanticerror import SchemaSemanticError

from ccai.provisioning.cloudinit.bootstrapsecrets import (
    BootstrapSecrets, IndexCredential
)


# pip / PyPI convention for token authentication over HTTP basic auth.
TOKEN_USERNAME = "__token__"

_ACCEPTED_CLASSES = (
    BasicCredential, PersonalApiTokenCredential, ApiTokenCredential,
    SecretTokenCredential,
)


def resolve_index_credential(*, spec: PythonEnvironmentSpec,
                             credential_lookup: Callable[[str], Any]
                             ) -> IndexCredential:
    """
        Resolve and type-check a spec's ``index_credential`` reference.

        Mirrors ``resolve_control_plane_credential``: the model never owns a
        vault, the caller supplies the lookup, and the resolved object must
        be one of the credential classes a package index can consume:

        - ``BasicCredential`` -> ``username`` / ``password``.
        - ``PersonalApiTokenCredential`` -> ``username`` / ``token``.
        - ``ApiTokenCredential`` / ``SecretTokenCredential`` ->
          ``__token__`` / ``token`` (the PyPI-style convention).

        :param spec: The spec naming the credential.
        :param credential_lookup: Maps a reference to a credential object;
                                  raising or returning ``None`` signals an
                                  unresolved reference.

        :returns: The :class:`IndexCredential`.

        :raises: SchemaSemanticError
    """
    reference = spec.index_credential
    if reference is None:
        raise SchemaSemanticError(
            "PythonEnvironmentSpec {!r} names no index_credential.".format(spec.path)
        )

    # ``ConfigurationError`` (what ``CredentialManager.lookup_credential``
    # raises for an unknown key) derives from ``BaseException``, so it is
    # named explicitly; a bare ``except Exception`` would let it escape.
    try:
        credential = credential_lookup(reference)
    except (Exception, ConfigurationError) as ex:
        err_msg_lines = ["Could not resolve the index credential for a Python environment."]
        err_msg_lines.append("PATH: {}".format(spec.path))
        err_msg_lines.append("INDEX_CREDENTIAL: {}".format(reference))
        err_msg_lines.append("REASON: {}".format(ex))
        err_msg = os.linesep.join(err_msg_lines)
        raise SchemaSemanticError(err_msg) from None

    if credential is None:
        err_msg_lines = ["The index credential reference did not resolve."]
        err_msg_lines.append("PATH: {}".format(spec.path))
        err_msg_lines.append("INDEX_CREDENTIAL: {}".format(reference))
        err_msg = os.linesep.join(err_msg_lines)
        raise SchemaSemanticError(err_msg)

    if isinstance(credential, BasicCredential):
        rtnval = IndexCredential(username=credential.username,
                                 secret=credential.password)
        return rtnval

    if isinstance(credential, PersonalApiTokenCredential):
        rtnval = IndexCredential(username=credential.username,
                                 secret=credential.token)
        return rtnval

    if isinstance(credential, (ApiTokenCredential, SecretTokenCredential)):
        rtnval = IndexCredential(username=TOKEN_USERNAME, secret=credential.token)
        return rtnval

    accepted = ", ".join(cls.__name__ for cls in _ACCEPTED_CLASSES)
    err_msg_lines = ["The index credential is not a class a package index can consume."]
    err_msg_lines.append("PATH: {}".format(spec.path))
    err_msg_lines.append("INDEX_CREDENTIAL: {}".format(reference))
    err_msg_lines.append("RESOLVED: {}".format(type(credential).__name__))
    err_msg_lines.append("ACCEPTED: {}".format(accepted))
    err_msg = os.linesep.join(err_msg_lines)
    raise SchemaSemanticError(err_msg)


def collect_bootstrap_secrets(*, instances: Iterable[Any],
                              credential_lookup: Callable[[str], Any]
                              ) -> BootstrapSecrets:
    """
        Resolve every ``index_credential`` named by the Python environments
        of the given instances into one :class:`BootstrapSecrets`.

        Each reference is resolved once even when several environments
        share it.

        :param instances: ``CloudInstance`` objects (or anything exposing
                          ``python_environments``).
        :param credential_lookup: Caller-supplied vault lookup.

        :returns: The populated container (empty when nothing names a
                  credential).

        :raises: SchemaSemanticError
    """
    rtnval = BootstrapSecrets()
    for instance in instances:
        environments = getattr(instance, "python_environments", None)
        if environments is None:
            continue
        for spec in environments:
            reference = spec.index_credential
            if reference is None or reference in rtnval.index_credentials:
                continue
            rtnval.index_credentials[reference] = resolve_index_credential(
                spec=spec, credential_lookup=credential_lookup,
            )
    return rtnval


__all__ = [
    "TOKEN_USERNAME",
    "collect_bootstrap_secrets",
    "resolve_index_credential",
]
