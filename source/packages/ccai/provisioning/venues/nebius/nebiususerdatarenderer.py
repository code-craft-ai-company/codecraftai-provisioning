"""
    .. module:: nebiususerdatarenderer
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Renderer placing a VPN-join cloud-init payload into a Nebius
        instance's metadata user-data slot.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, Optional

from ccai.provisioning.cloudinit.bootstraprenderer import (
    render_instance_user_data
)
from ccai.provisioning.model.cloud.cloudinstance import CloudInstance
from ccai.provisioning.model.vpn.hostnametemplate import render_hostname


class NebiusUserDataRenderer:
    """
        Renderer for the Nebius instance ``metadata["user-data"]`` slot.

        When an instance carries a ``vpn_join`` spec, the M6
        :func:`render_instance_user_data` helper produces the cloud-init dict; this
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
        rendered_hostname: Optional[str] = None
        if instance.vpn_join is not None:
            context: Dict[str, Any] = {"instance_name": instance.name}
            rendered_hostname = render_hostname(
                template=instance.vpn_join.hostname_template, context=context,
            )

        # The shared composer folds VPN join, Python environments and the
        # raw user_data_script into one document; a raw script alone
        # passes through verbatim.
        rtnval = render_instance_user_data(
            instance=instance, authkey=authkey,
            rendered_hostname=rendered_hostname,
        )
        return rtnval
