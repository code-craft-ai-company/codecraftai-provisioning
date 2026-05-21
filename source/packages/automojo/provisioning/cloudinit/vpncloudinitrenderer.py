"""
    .. module:: vpncloudinitrenderer
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Renderer producing cloud-init payloads for VPN-join bootstrap.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Any, Dict, List

from automojo.provisioning.model.vpn.vpnjoinspec import VPNJoinSpec
from automojo.provisioning.cloudinit.cloudinitrenderererror import (
    CloudInitRendererError
)
from automojo.provisioning.cloudinit.secretquoting import (
    quote_for_shell, write_authkey_file_block
)


SUPPORTED_LINUX_FAMILIES = frozenset({
    "ubuntu", "debian", "rhel", "fedora", "amazonlinux"
})
SUPPORTED_WINDOWS_FAMILIES = frozenset({"windows-server"})


def _validate_image_family(*, image_family: str) -> None:
    """
        Reject unsupported image families.

        :param image_family: The image family.

        :raises: CloudInitRendererError
    """
    if image_family in SUPPORTED_LINUX_FAMILIES:
        return
    if image_family in SUPPORTED_WINDOWS_FAMILIES:
        return

    supported = sorted(SUPPORTED_LINUX_FAMILIES | SUPPORTED_WINDOWS_FAMILIES)
    err_msg_lines = ["Unsupported image_family for cloud-init renderer."]
    err_msg_lines.append("SUPPORTED: {}".format(", ".join(supported)))
    err_msg_lines.append("ACTUAL: {!r}".format(image_family))
    err_msg = os.linesep.join(err_msg_lines)
    raise CloudInitRendererError(err_msg)


def _install_command_for(*, image_family: str, provider: str) -> List[Any]:
    """
        Return the cloud-init runcmd entry that installs the daemon.

        :param image_family: One of the supported Linux families.
        :param provider: tailscale or twingate.

        :returns: A runcmd list entry.
    """
    if provider == "tailscale":
        rtnval = ["sh", "-c",
                  "curl -fsSL https://tailscale.com/install.sh | sh"]
        return rtnval

    if image_family in {"ubuntu", "debian"}:
        cmd = (
            "curl -fsSL "
            "https://binaries.twingate.com/connector/setup.sh "
            "| bash"
        )
        rtnval = ["sh", "-c", cmd]
        return rtnval

    cmd = (
        "curl -fsSL "
        "https://binaries.twingate.com/connector/setup.sh "
        "| bash"
    )
    rtnval = ["sh", "-c", cmd]
    return rtnval


def _build_tailscale_bringup(*, rendered_hostname: str,
                             advertise_tags: List[str],
                             advertise_routes: List[str],
                             exit_node: bool) -> str:
    """
        Build the tailscale bring-up script body.

        Auth key is read from a root-only file at runtime, never
        interpolated into the YAML scalar.  Hostname and tags are quoted
        with shell-safe single quotes against injection.

        :param rendered_hostname: Hostname for ``--hostname``.
        :param advertise_tags: List of tag strings.
        :param advertise_routes: List of CIDR strings.
        :param exit_node: Whether to advertise as exit node.

        :returns: The shell script body.
    """
    host_quoted = quote_for_shell(value=rendered_hostname)
    tag_joined = ",".join(advertise_tags)
    tag_quoted = quote_for_shell(value=tag_joined)

    lines: List[str] = []
    lines.append("#!/bin/bash")
    lines.append("set -euo pipefail")
    lines.append("AUTHKEY=\"$(cat /etc/tailscale/authkey)\"")
    lines.append("HOST={}".format(host_quoted))
    lines.append("TAGS={}".format(tag_quoted))
    cmd_parts = [
        "tailscale up",
        "  --auth-key=\"${AUTHKEY}\"",
        "  --hostname=\"${HOST}\"",
        "  --advertise-tags=\"${TAGS}\"",
    ]

    if len(advertise_routes) > 0:
        routes_joined = ",".join(advertise_routes)
        routes_quoted = quote_for_shell(value=routes_joined)
        lines.append("ROUTES={}".format(routes_quoted))
        cmd_parts.append("  --advertise-routes=\"${ROUTES}\"")

    if exit_node is True:
        cmd_parts.append("  --advertise-exit-node")

    lines.append(" \\\n".join(cmd_parts))
    rtnval = "\n".join(lines) + "\n"
    return rtnval


def _build_twingate_bringup(*, advertise_routes: List[str]) -> str:
    """
        Build the Twingate connector bring-up script.

        :param advertise_routes: Optional advertised CIDRs (informational).

        :returns: The shell script body.
    """
    lines: List[str] = []
    lines.append("#!/bin/bash")
    lines.append("set -euo pipefail")
    lines.append("TOKEN=\"$(cat /etc/twingate/connector.conf)\"")
    lines.append("export TWINGATE_ACCESS_TOKEN=\"${TOKEN}\"")
    lines.append("systemctl enable twingate-connector")
    lines.append("systemctl start twingate-connector")
    for cidr in advertise_routes:
        quoted = quote_for_shell(value=cidr)
        lines.append("echo route={} >> /etc/twingate/routes.list".format(
            quoted
        ))
    rtnval = "\n".join(lines) + "\n"
    return rtnval


def render_cloud_init(*, spec: VPNJoinSpec, authkey: str,
                      rendered_hostname: str,
                      image_family: str) -> Dict[str, Any]:
    """
        Render the cloud-init YAML fragment for the given VPN join spec.

        :param spec: The VPNJoinSpec.
        :param authkey: Minted auth key (Tailscale) or connector token
                        (Twingate).
        :param rendered_hostname: Hostname computed from the host template.
        :param image_family: Image family (ubuntu, debian, rhel, ...).

        :returns: A dict suitable for ``yaml.safe_dump``.
        :raises: CloudInitRendererError
    """
    _validate_image_family(image_family=image_family)

    advertise_tags = list(spec.advertise_tags) if spec.advertise_tags is not None else []
    advertise_routes = list(spec.advertise_routes) if spec.advertise_routes is not None else []

    write_files: List[Dict[str, Any]] = []
    runcmd: List[Any] = []

    if spec.provider == "tailscale":
        write_files.append(write_authkey_file_block(authkey=authkey))
        bringup = _build_tailscale_bringup(
            rendered_hostname=rendered_hostname,
            advertise_tags=advertise_tags,
            advertise_routes=advertise_routes,
            exit_node=spec.exit_node,
        )
        write_files.append({
            "path": "/etc/tailscale/bringup.sh",
            "owner": "root:root",
            "permissions": "0700",
            "content": bringup,
        })
        runcmd.append(_install_command_for(image_family=image_family,
                                           provider="tailscale"))
        runcmd.append(["/etc/tailscale/bringup.sh"])
    elif spec.provider == "twingate":
        write_files.append({
            "path": "/etc/twingate/connector.conf",
            "owner": "root:root",
            "permissions": "0400",
            "content": authkey,
        })
        bringup = _build_twingate_bringup(advertise_routes=advertise_routes)
        write_files.append({
            "path": "/etc/twingate/bringup.sh",
            "owner": "root:root",
            "permissions": "0700",
            "content": bringup,
        })
        runcmd.append(_install_command_for(image_family=image_family,
                                           provider="twingate"))
        runcmd.append(["/etc/twingate/bringup.sh"])
    else:
        err_msg = "Unsupported VPN provider: {!r}".format(spec.provider)
        raise CloudInitRendererError(err_msg)

    rtnval: Dict[str, Any] = {
        "write_files": write_files,
        "runcmd": runcmd,
    }
    return rtnval


def render_azure_cse(*, spec: VPNJoinSpec, authkey: str,
                     rendered_hostname: str,
                     image_family: str) -> Dict[str, Any]:
    """
        Render the Azure Custom Script Extension payload.

        :param spec: VPNJoinSpec.
        :param authkey: Minted auth key.
        :param rendered_hostname: Hostname for the VM.
        :param image_family: Image family.

        :returns: A dict with ``settings`` and ``protectedSettings`` keys.
        :raises: CloudInitRendererError
    """
    _validate_image_family(image_family=image_family)

    if image_family in SUPPORTED_WINDOWS_FAMILIES:
        host_quoted = rendered_hostname.replace("'", "''")
        tags = list(spec.advertise_tags) if spec.advertise_tags is not None else []
        tag_arg = ",".join(tags).replace("'", "''")
        ps_lines: List[str] = []
        ps_lines.append("$ErrorActionPreference = 'Stop'")
        ps_lines.append(
            "Invoke-WebRequest "
            "https://pkgs.tailscale.com/stable/tailscale-setup.exe "
            "-OutFile tailscale-setup.exe"
        )
        ps_lines.append("./tailscale-setup.exe /quiet")
        ps_lines.append(
            "tailscale up "
            "--auth-key='{}' --hostname='{}' --advertise-tags='{}'".format(
                authkey.replace("'", "''"), host_quoted, tag_arg
            )
        )
        ps_script = "; ".join(ps_lines)
        command_to_execute = (
            "powershell -ExecutionPolicy Unrestricted -Command \""
            + ps_script.replace("\"", "\\\"")
            + "\""
        )
        # The auth key is embedded in commandToExecute. The Azure CSE
        # treats the ``settings`` block as public (visible in plain VM
        # extension settings) and the ``protectedSettings`` block as
        # encrypted; the secret-bearing commandToExecute therefore lives
        # in protectedSettings, never in the public settings block.
        rtnval = {
            "settings": {
                "fileUris": [],
            },
            "protectedSettings": {
                "commandToExecute": command_to_execute,
            },
        }
        return rtnval

    # Linux family — wrap the cloud-init renderer's runcmd as a shell script.
    base = render_cloud_init(spec=spec, authkey=authkey,
                             rendered_hostname=rendered_hostname,
                             image_family=image_family)
    shell_lines: List[str] = []
    for write_file in base["write_files"]:
        path_q = quote_for_shell(value=write_file["path"])
        content_q = quote_for_shell(value=write_file["content"])
        perms_q = quote_for_shell(value=write_file["permissions"])
        shell_lines.append(
            "install -m {} /dev/null {}; printf %s {} > {}".format(
                perms_q, path_q, content_q, path_q
            )
        )
    for entry in base["runcmd"]:
        if isinstance(entry, list):
            shell_lines.append(" ".join(entry))
        else:
            shell_lines.append(str(entry))

    # The shell script writes the auth-key file content (a secret) inline.
    # Place the secret-bearing commandToExecute in protectedSettings (the
    # Azure-encrypted block) and never in the public ``settings`` block.
    rtnval = {
        "settings": {
            "fileUris": [],
        },
        "protectedSettings": {
            "commandToExecute": "; ".join(shell_lines),
        },
    }
    return rtnval


def render_vsphere_guest_customization(*, spec: VPNJoinSpec, authkey: str,
                                       rendered_hostname: str,
                                       image_family: str
                                       ) -> Dict[str, Any]:
    """
        Render the vSphere VmGuestCustomizationSpec-compatible payload.

        :param spec: VPNJoinSpec.
        :param authkey: Minted auth key.
        :param rendered_hostname: Hostname for the guest.
        :param image_family: Image family.

        :returns: A dict with ``userData`` (Linux) or ``runOnceCommands``
                  (Windows).
        :raises: CloudInitRendererError
    """
    _validate_image_family(image_family=image_family)

    if image_family in SUPPORTED_WINDOWS_FAMILIES:
        cse = render_azure_cse(spec=spec, authkey=authkey,
                               rendered_hostname=rendered_hostname,
                               image_family=image_family)
        command_to_execute = cse["protectedSettings"]["commandToExecute"]
        rtnval = {
            "hostname": rendered_hostname,
            "runOnceCommands": [command_to_execute],
        }
        return rtnval

    base = render_cloud_init(spec=spec, authkey=authkey,
                             rendered_hostname=rendered_hostname,
                             image_family=image_family)
    rtnval = {
        "hostname": rendered_hostname,
        "userData": base,
    }
    return rtnval
