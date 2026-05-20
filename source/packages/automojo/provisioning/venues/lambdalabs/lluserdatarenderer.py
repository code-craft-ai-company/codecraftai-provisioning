"""
    .. module:: lluserdatarenderer
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: LlUserDataRenderer — renders the launch ``user_data`` field
               for the Lambda Labs venue from a neutral CloudInstance.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Optional

import yaml

from automojo.provisioning.cloudinit.vpncloudinitrenderer import (
    render_cloud_init
)
from automojo.provisioning.model.cloud.cloudinstance import CloudInstance


class LlUserDataRenderer:
    """
        Renders the Lambda Labs launch ``user_data`` payload.

        When a :class:`CloudInstance` carries a ``vpn_join`` spec the
        renderer delegates to the M6 :func:`render_cloud_init` to produce
        the cloud-init document, then serialises it to a ``#cloud-config``
        YAML string suitable for the Lambda Labs launch request.  When the
        instance carries only a raw ``user_data_script`` that script is
        returned verbatim.
    """

    def render(self, *, instance: CloudInstance, authkey: str,
               rendered_hostname: str) -> Optional[str]:
        """
            Render the launch ``user_data`` string for an instance.

            :param instance: The neutral :class:`CloudInstance`.
            :param authkey: The minted VPN auth key (or connector token).
            :param rendered_hostname: The per-instance hostname.

            :returns: The ``user_data`` string, or ``None`` when the
                instance needs no launch metadata.
        """
        vpn_join = instance.vpn_join
        if vpn_join is not None:
            image_family = instance.image.family
            cloud_init_doc = render_cloud_init(
                spec=vpn_join, authkey=authkey,
                rendered_hostname=rendered_hostname,
                image_family=image_family,
            )
            body = yaml.safe_dump(cloud_init_doc, default_flow_style=False,
                                  sort_keys=True)
            rtnval = "#cloud-config\n" + body
            return rtnval

        script = instance.user_data_script
        if script is not None and len(script) > 0:
            rtnval = script
            return rtnval

        rtnval = None
        return rtnval
