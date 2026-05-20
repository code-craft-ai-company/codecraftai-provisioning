"""
    .. module:: nebiususerdatarenderer
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Renderer placing a VPN-join cloud-init payload into a Nebius
        instance's metadata user-data slot.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, Optional

import yaml

from automojo.provisioning.cloudinit.vpncloudinitrenderer import (
    render_cloud_init
)
from automojo.provisioning.model.cloud.cloudinstance import CloudInstance
from automojo.provisioning.model.vpn.hostnametemplate import render_hostname


class NebiusUserDataRenderer:
    """
        Renderer for the Nebius instance ``metadata["user-data"]`` slot.

        When an instance carries a ``vpn_join`` spec, the M6
        :func:`render_cloud_init` helper produces the cloud-init dict; this
        renderer serialises it to a ``#cloud-config`` document and returns it
        for placement into the Nebius launch metadata.
    """

    def render(self, *, instance: CloudInstance,
               authkey: str) -> Optional[str]:
        """
            Render the user-data document for an instance.

            :param instance: The :class:`CloudInstance` being launched.
            :param authkey: The minted VPN auth key / connector token.

            :returns: A ``#cloud-config`` document string, or ``None`` when
                the instance declares neither a raw user-data script nor a
                VPN join spec.
        """
        if instance.vpn_join is None:
            if instance.user_data_script is None:
                rtnval: Optional[str] = None
                return rtnval
            if len(instance.user_data_script) == 0:
                rtnval = None
                return rtnval
            rtnval = instance.user_data_script
            return rtnval

        context: Dict[str, Any] = {"instance_name": instance.name}
        rendered_hostname = render_hostname(
            template=instance.vpn_join.hostname_template, context=context,
        )

        cloud_init_doc = render_cloud_init(
            spec=instance.vpn_join, authkey=authkey,
            rendered_hostname=rendered_hostname,
            image_family=instance.image.family,
        )

        document = "#cloud-config\n" + yaml.safe_dump(
            cloud_init_doc, default_flow_style=False, sort_keys=True,
        )
        rtnval = document
        return rtnval
