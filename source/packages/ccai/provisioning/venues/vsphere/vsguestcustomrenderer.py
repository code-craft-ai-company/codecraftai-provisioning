"""
    .. module:: vsguestcustomrenderer
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: VsGuestCustomRenderer — builds the guest-customisation payload
        (cloud-init for Linux, sysprep for Windows) for a CloudInstance,
        injecting CloudKeyPair material and VPNJoinSpec bootstrap.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Any, Dict, List, Optional

import yaml

from ccai.provisioning.cloudinit.cloudinitmerge import merge_cloud_init_fragments
from ccai.provisioning.cloudinit.pythonenvcloudinitrenderer import (
    render_python_env_cloud_init
)
from ccai.provisioning.cloudinit.vpncloudinitrenderer import (
    is_windows_family, render_vsphere_guest_customization
)
from ccai.provisioning.model.cloud.cloudinstance import CloudInstance


class VsGuestCustomization:
    """
        Resolved guest-customisation payload for a single VM.

        Carries the rendered hostname, the guest OS family (``linux`` or
        ``windows``), and the ``cloud_init.user_data`` body (a
        ``#cloud-config`` document for Linux, or a sysprep command list for
        Windows) ready to hand to the interop client.
    """

    def __init__(self, *, hostname: str, guest_os_family: str,
                 cloud_init_user_data: str,
                 raw_payload: Dict[str, Any]) -> None:
        """
            Construct a VsGuestCustomization.

            :param hostname: The rendered guest hostname.
            :param guest_os_family: ``linux`` or ``windows``.
            :param cloud_init_user_data: The rendered user-data body.
            :param raw_payload: The structured payload dict.
        """
        self.hostname: str = hostname
        self.guest_os_family: str = guest_os_family
        self.cloud_init_user_data: str = cloud_init_user_data
        self.raw_payload: Dict[str, Any] = raw_payload
        return


def _guest_os_family_for(*, image_family: str) -> str:
    """
        Classify a neutral image family as a vSphere guest OS family.

        :param image_family: The neutral image family.

        :returns: ``windows`` or ``linux``.
    """
    if is_windows_family(image_family=image_family):
        rtnval = "windows"
        return rtnval
    rtnval = "linux"
    return rtnval


def _merge_keypair_users(*, cloud_init: Dict[str, Any],
                         public_key_material: Optional[str]) -> None:
    """
        Inject a CloudKeyPair public key into the cloud-init ``users`` block.

        :param cloud_init: The cloud-init document dict (modified in place).
        :param public_key_material: OpenSSH public key string, or None.
    """
    if public_key_material is None or len(public_key_material) == 0:
        return

    users = cloud_init.get("users", None)
    if users is None:
        users = []
        cloud_init["users"] = users

    users.append({
        "name": "ccai",
        "sudo": "ALL=(ALL) NOPASSWD:ALL",
        "shell": "/bin/bash",
        "ssh_authorized_keys": [public_key_material],
    })
    return


class VsGuestCustomRenderer:
    """
        Builds the guest-customisation payload for a :class:`CloudInstance`.

        Linux instances receive a cloud-init ``#cloud-config`` body; Windows
        instances receive a sysprep run-once command list.  When the
        instance carries a ``vpn_join`` the M6 ``render_cloud_init`` helper's
        VPN bootstrap is woven into the same payload, so the VPN join travels
        through guest customisation identically to AWS user-data.
    """

    def render(self, *, instance: CloudInstance,
               keypair_material: Optional[str] = None,
               authkey: Optional[str] = None) -> VsGuestCustomization:
        """
            Render the guest-customisation payload for an instance.

            :param instance: The CloudInstance being realised.
            :param keypair_material: Optional OpenSSH public key for the
                                     instance's CloudKeyPair.
            :param authkey: Optional minted VPN auth-key / connector token.

            :returns: A :class:`VsGuestCustomization`.
        """
        image_family = instance.image.family
        guest_os_family = _guest_os_family_for(image_family=image_family)

        if instance.vpn_join is not None:
            rendered_hostname = instance.vpn_join.hostname_template.replace(
                "{instance_name}", instance.name
            )
            effective_authkey = authkey if authkey is not None else ""
            payload = render_vsphere_guest_customization(
                spec=instance.vpn_join,
                authkey=effective_authkey,
                rendered_hostname=rendered_hostname,
                image_family=image_family,
            )
        else:
            rendered_hostname = instance.name
            payload = {"hostname": rendered_hostname}
            if guest_os_family == "linux":
                payload["userData"] = {"write_files": [], "runcmd": []}
            else:
                payload["runOnceCommands"] = []

        if guest_os_family == "linux":
            cloud_init = payload.get("userData", {})
            # Python environments are a Linux-only first-boot fragment;
            # merge it ahead of the raw script so the script can rely on
            # the environments existing.
            python_environments = instance.python_environments
            if python_environments is not None and len(python_environments) > 0:
                python_fragment = render_python_env_cloud_init(
                    specs=python_environments, image_family=image_family,
                )
                cloud_init = merge_cloud_init_fragments(cloud_init, python_fragment)
                payload["userData"] = cloud_init
            if instance.user_data_script is not None and len(instance.user_data_script) > 0:
                extra_runcmd = cloud_init.get("runcmd", None)
                if extra_runcmd is None:
                    extra_runcmd = []
                    cloud_init["runcmd"] = extra_runcmd
                extra_runcmd.append(["sh", "-c", instance.user_data_script])
            _merge_keypair_users(cloud_init=cloud_init,
                                 public_key_material=keypair_material)
            body_lines: List[str] = ["#cloud-config"]
            body_lines.append(yaml.safe_dump(cloud_init, sort_keys=False))
            user_data = "\n".join(body_lines)
        else:
            commands = payload.get("runOnceCommands", [])
            user_data = os.linesep.join(commands)

        rtnval = VsGuestCustomization(
            hostname=rendered_hostname,
            guest_os_family=guest_os_family,
            cloud_init_user_data=user_data,
            raw_payload=payload,
        )
        return rtnval
