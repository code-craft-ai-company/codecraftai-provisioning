"""
    .. module:: vpncleanup
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared best-effort VPN device de-registration helper for the
        cloud / workload venue provisioners.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import logging

from typing import Any

from automojo.errors.exceptions import SemanticError
from automojo.provisioning.model.exceptions import SchemaSemanticError


logger = logging.getLogger(__name__)


def delete_vpn_device(*, vpn_control_plane: Any, device_id: str,
                      aspects: Any) -> bool:
    """
        De-register a single VPN device on a best-effort basis.

        Destroy is reverse-order teardown; a control-plane device that is
        already gone (or a transient API error) must not abort the rest of
        the teardown.  The failure is logged rather than silently swallowed
        so it remains debuggable, and a :class:`SemanticError` /
        :class:`SchemaSemanticError` is never caught — an API-misuse defect
        must bubble per the project exception-handling discipline.

        :param vpn_control_plane: The ``IVPNControlPlane`` implementation.
        :param device_id: The provider-assigned VPN device identifier.
        :param aspects: Behaviour control propagated into the call.

        :returns: ``True`` when the device was de-registered, ``False`` when
            the call failed and the failure was logged.

        :raises: SemanticError, SchemaSemanticError
    """
    rtnval = False
    try:
        vpn_control_plane.delete_device(device_id=device_id,
                                        aspects=aspects)
        rtnval = True
    except (SemanticError, SchemaSemanticError):
        raise
    except Exception as cleanup_error:
        logger.warning(
            "Best-effort VPN device de-registration failed for "
            "device_id=%s: %s", device_id, cleanup_error)
        rtnval = False

    return rtnval
