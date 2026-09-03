"""
    .. module:: vpncredentialresolver
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Validate-time resolver for a VPNJoinSpec control-plane credential.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Any, Callable

from ccai.credentials.tailscaleoauthcredential import TailscaleOAuthCredential
from ccai.credentials.tailscaleauthkeycredential import (
    TailscaleAuthKeyCredential
)
from ccai.credentials.twingateserviceaccountcredential import (
    TwingateServiceAccountCredential
)

from ccai.errors.exceptions import ConfigurationError
from ccai.interfaces.schemasemanticerror import SchemaSemanticError
from ccai.interfaces.vpnjoinspec import VPNJoinSpec


# Per provider, the set of credential classes the control plane accepts.
# The model never owns a global vault; the caller supplies the lookup.
_PROVIDER_CREDENTIAL_CLASSES = {
    "tailscale": (TailscaleOAuthCredential, TailscaleAuthKeyCredential),
    "twingate": (TwingateServiceAccountCredential,),
}


def resolve_control_plane_credential(*, spec: VPNJoinSpec,
                                     credential_lookup: Callable[[str], Any]
                                     ) -> Any:
    """
        Resolve and type-check a VPNJoinSpec control-plane credential.

        The :class:`VPNJoinSpec` carries ``control_plane_credential`` as a bare
        string reference.  This lifecycle hook resolves that reference through a
        caller-supplied lookup (Aspects-pattern: the model never owns a global
        vault) and verifies the resolved credential is the right class for the
        declared provider:

        - ``tailscale`` resolves to a ``TailscaleOAuthCredential`` or a
          ``TailscaleAuthKeyCredential``.
        - ``twingate`` resolves to a ``TwingateServiceAccountCredential``.

        :param spec: The VPNJoinSpec whose credential is being resolved.
        :param credential_lookup: A caller-supplied callable that maps a
                                  credential reference string to a credential
                                  object; raising or returning None signals an
                                  unresolved reference.

        :returns: The resolved, type-checked credential object.
        :raises: SchemaSemanticError on a missing or mismatched credential.
    """
    reference = spec.control_plane_credential

    # ``ConfigurationError`` — what ``CredentialManager.lookup_credential``
    # raises for an unknown key — derives from ``BaseException``, so it must
    # be named explicitly or it escapes validate as a raw error.
    try:
        resolved = credential_lookup(reference)
    except (LookupError, ValueError, RuntimeError, ConfigurationError) as xcpt:
        err_msg_lines = ["Failed to resolve VPN control-plane credential."]
        err_msg_lines.append("PROVIDER: {}".format(spec.provider))
        err_msg_lines.append("REFERENCE: {!r}".format(reference))
        err_msg_lines.append("CAUSE: {}".format(xcpt))
        err_msg = os.linesep.join(err_msg_lines)
        raise SchemaSemanticError(err_msg) from None

    if resolved is None:
        err_msg_lines = ["VPN control-plane credential did not resolve."]
        err_msg_lines.append("PROVIDER: {}".format(spec.provider))
        err_msg_lines.append("REFERENCE: {!r}".format(reference))
        err_msg = os.linesep.join(err_msg_lines)
        raise SchemaSemanticError(err_msg)

    expected_classes = _PROVIDER_CREDENTIAL_CLASSES.get(spec.provider, None)
    if expected_classes is None:
        err_msg_lines = ["VPNJoinSpec provider has no credential contract."]
        err_msg_lines.append("PROVIDER: {!r}".format(spec.provider))
        err_msg = os.linesep.join(err_msg_lines)
        raise SchemaSemanticError(err_msg)

    if not isinstance(resolved, expected_classes):
        expected_names = [cls.__name__ for cls in expected_classes]
        err_msg_lines = [
            "VPN control-plane credential is the wrong class for its provider."
        ]
        err_msg_lines.append("PROVIDER: {}".format(spec.provider))
        err_msg_lines.append("REFERENCE: {!r}".format(reference))
        err_msg_lines.append(
            "EXPECTED: one of {}".format(", ".join(expected_names))
        )
        err_msg_lines.append("ACTUAL: {}".format(type(resolved).__name__))
        err_msg = os.linesep.join(err_msg_lines)
        raise SchemaSemanticError(err_msg)

    rtnval = resolved
    return rtnval
