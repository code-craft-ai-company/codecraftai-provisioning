"""
    .. module:: metaluserdatarenderer
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: MetalUserDataRenderer — renders the Device ``userdata`` field,
               including the VPN-join cloud-init snippet.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import List

import yaml

from ccai.provisioning.cloudinit.vpncloudinitrenderer import (
    render_cloud_init
)
from ccai.provisioning.model.cloud.cloudinstance import CloudInstance


class MetalUserDataRenderer:
    """
        Renders the cloud-init body used as the Equinix Metal Device
        ``userdata`` field.

        Equinix Metal passes the ``userdata`` string verbatim to the device's
        first-boot cloud-init.  Unlike AWS this is not base64-encoded — the
        plain ``#cloud-config`` YAML body is supplied directly.
    """

    def render(self, *, instance: CloudInstance, authkey: str) -> str:
        """
            Render the cloud-init body for the device.

            :param instance: The neutral CloudInstance.
            :param authkey: Minted VPN auth-key (used only when ``vpn_join``
                            is declared).

            :returns: A ``#cloud-config`` YAML body, or the raw user-data
                      script (or "") when no ``vpn_join`` is declared.
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
