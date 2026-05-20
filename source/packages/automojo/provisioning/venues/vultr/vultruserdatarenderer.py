"""
    .. module:: vultruserdatarenderer
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: VultrUserDataRenderer — renders cloud-init user_data for Vultr.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import base64

from typing import List

import yaml

from automojo.provisioning.cloudinit.vpncloudinitrenderer import (
    render_cloud_init
)
from automojo.provisioning.model.cloud.cloudinstance import CloudInstance


class VultrUserDataRenderer:
    """
        Renderer producing the base64 ``user_data`` body Vultr requires for
        instance creation.

        Vultr accepts a base64-encoded cloud-init payload on the
        ``POST /instances`` call.  When an instance carries a ``vpn_join``
        spec the M6 :func:`render_cloud_init` renderer produces the
        cloud-config body; otherwise any raw ``user_data_script`` is used.
    """

    def render_body(self, *, instance: CloudInstance, authkey: str) -> str:
        """
            Render the cloud-init body for the instance.

            :param instance: The CloudInstance.
            :param authkey: Minted VPN auth-key value (used when vpn_join set).

            :returns: A ``#cloud-config`` body, or "" when no payload applies.
        """
        if instance.vpn_join is None:
            base_script = instance.user_data_script
            rtnval = base_script if base_script is not None else ""
            return rtnval

        rendered_hostname = instance.vpn_join.hostname_template.replace(
            "{instance_name}", instance.name
        )
        cloud_init = render_cloud_init(
            spec=instance.vpn_join,
            authkey=authkey,
            rendered_hostname=rendered_hostname,
            image_family=instance.image.family,
        )

        body_lines: List[str] = ["#cloud-config"]
        body_lines.append(yaml.safe_dump(cloud_init, sort_keys=False))
        rtnval = "\n".join(body_lines)
        return rtnval

    def render_base64(self, *, instance: CloudInstance,
                      authkey: str) -> str:
        """
            Render the base64-encoded ``user_data`` body for Vultr.

            :param instance: The CloudInstance.
            :param authkey: Minted VPN auth-key value.

            :returns: A base64 string, or "" when there is no body.
        """
        body = self.render_body(instance=instance, authkey=authkey)
        if body is None or len(body) == 0:
            rtnval = ""
            return rtnval

        encoded = base64.b64encode(body.encode("utf-8")).decode("ascii")
        rtnval = encoded
        return rtnval
