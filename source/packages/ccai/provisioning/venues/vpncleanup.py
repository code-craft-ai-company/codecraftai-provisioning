"""
    .. module:: vpncleanup
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared best-effort VPN device de-registration helper for the
        cloud / workload venue provisioners.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import logging

from typing import Any, List

from ccai.errors.exceptions import SemanticError
from ccai.interfaces.schemasemanticerror import SchemaSemanticError


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


def deregister_devices_by_hostname(*, vpn_control_plane: Any,
                                   hostnames: List[str],
                                   aspects: Any) -> List[str]:
    """
        De-register every VPN device whose hostname matches an expected one.

        Device ids are resolved *durably* from the control plane at destroy
        time rather than from apply-process memory: the join hostname of each
        resource is deterministic and recomputable from the spec, so a fresh
        destroy process (the normal apply-now / destroy-later flow) can list
        the control plane's devices and match them by hostname.  This replaces
        the per-venue in-memory device-id lists that were always empty on a
        separate destroy invocation.

        Best-effort: a control-plane list failure is logged and treated as
        "nothing to de-register" so it never aborts the rest of teardown, but
        a :class:`SemanticError` / :class:`SchemaSemanticError` is never
        caught.

        :param vpn_control_plane: The ``IVPNControlPlane`` implementation, or
            ``None``.
        :param hostnames: The expected join hostnames of this run's devices.
        :param aspects: Behaviour control propagated into the calls.

        :returns: The list of de-registered device ids.

        :raises: SemanticError, SchemaSemanticError
    """
    deleted: List[str] = []
    if vpn_control_plane is None:
        return deleted
    if hostnames is None or len(hostnames) == 0:
        return deleted

    wanted = set(hostnames)

    try:
        devices = vpn_control_plane.list_devices(aspects=aspects)
    except (SemanticError, SchemaSemanticError):
        raise
    except Exception as list_error:
        logger.warning(
            "Best-effort VPN device de-registration could not list control-"
            "plane devices: %s", list_error)
        return deleted

    for device in devices:
        hostname = getattr(device, "hostname", None)
        if hostname is None or hostname not in wanted:
            continue
        device_id = getattr(device, "device_id", None)
        if device_id is None or len(str(device_id)) == 0:
            continue
        deregistered = delete_vpn_device(
            vpn_control_plane=vpn_control_plane, device_id=device_id,
            aspects=aspects)
        if deregistered is True:
            deleted.append(device_id)

    return deleted
