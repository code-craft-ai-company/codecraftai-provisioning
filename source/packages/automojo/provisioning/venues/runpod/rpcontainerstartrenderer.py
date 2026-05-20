"""
    .. module:: rpcontainerstartrenderer
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: RpContainerStartRenderer — renders a deterministic RunPod
        container start script that brings up userspace-mode Tailscale when a
        workload carries a VPNJoinSpec.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import hashlib

from typing import Any, List, Optional


# RunPod containers run without NET_ADMIN by default and have no
# /dev/net/tun device, so Tailscale must run in userspace networking mode.
_USERSPACE_FLAG = "--tun=userspace-networking"


class RpContainerStartRenderer:
    """
        Renders a RunPod container start script.

        RunPod pods are containers, not VMs — there is no cloud-init. The
        bring-up logic is instead a shell script handed to the pod as its
        ``dockerArgs`` / container start command. When a workload carries a
        :class:`VPNJoinSpec` the renderer prepends a userspace-mode Tailscale
        install + ``tailscale up`` block, since RunPod containers lack
        ``NET_ADMIN`` and a TUN device. For the same inputs the rendered
        script is byte-for-byte deterministic.
    """

    def render(self, *, workload: Any, vpn_join: Optional[Any],
               authkey: Optional[str] = None,
               hostname: Optional[str] = None) -> str:
        """
            Render the container start script for a workload.

            :param workload: The :class:`WorkloadJob` / :class:`WorkloadService`.
            :param vpn_join: The :class:`VPNJoinSpec`, or ``None`` when the
                workload does not join a VPN.
            :param authkey: An ephemeral Tailscale auth key. Only consumed
                when ``vpn_join`` is set; placeholder-substituted when
                ``None`` so the script stays deterministic for hashing.
            :param hostname: The Tailscale hostname for the pod.

            :returns: The rendered container start script.
        """
        lines: List[str] = ["#!/bin/sh", "set -e"]

        if vpn_join is not None:
            vpn_lines = self._render_tailscale_block(vpn_join=vpn_join,
                                                     authkey=authkey,
                                                     hostname=hostname)
            for entry in vpn_lines:
                lines.append(entry)

        command = getattr(workload, "command", None)
        if command is not None and len(command) > 0:
            lines.append("exec {}".format(" ".join(command)))
        else:
            lines.append("exec sleep infinity")

        rtnval = "\n".join(lines) + "\n"
        return rtnval

    def _render_tailscale_block(self, *, vpn_join: Any,
                                authkey: Optional[str],
                                hostname: Optional[str]) -> List[str]:
        """
            Render the userspace-mode Tailscale install + bring-up block.

            :param vpn_join: The :class:`VPNJoinSpec`.
            :param authkey: The ephemeral auth key, or ``None``.
            :param hostname: The Tailscale hostname, or ``None``.

            :returns: The list of script lines.
        """
        effective_key = authkey
        if effective_key is None:
            effective_key = "${TS_AUTHKEY}"

        effective_hostname = hostname
        if effective_hostname is None:
            effective_hostname = getattr(vpn_join, "hostname_template",
                                         "runpod-pod")

        up_args = ["tailscale", "up", _USERSPACE_FLAG,
                   "--authkey={}".format(effective_key),
                   "--hostname={}".format(effective_hostname)]

        if getattr(vpn_join, "ephemeral", True) is True:
            up_args.append("--ephemeral")

        advertise_tags = getattr(vpn_join, "advertise_tags", None)
        if advertise_tags is not None and len(advertise_tags) > 0:
            up_args.append("--advertise-tags={}".format(
                ",".join(advertise_tags)))

        advertise_routes = getattr(vpn_join, "advertise_routes", None)
        if advertise_routes is not None and len(advertise_routes) > 0:
            up_args.append("--advertise-routes={}".format(
                ",".join(advertise_routes)))

        lines = [
            "curl -fsSL https://tailscale.com/install.sh | sh",
            "tailscaled {} --state=mem: &".format(_USERSPACE_FLAG),
            " ".join(up_args),
        ]
        rtnval = lines
        return rtnval

    def content_hash(self, *, script: str) -> str:
        """
            Return the SHA-256 hex digest of a rendered start script.

            :param script: The rendered start script.

            :returns: The hex digest string.
        """
        digest = hashlib.sha256(script.encode("utf-8")).hexdigest()
        rtnval = digest
        return rtnval


__all__ = ["RpContainerStartRenderer"]
