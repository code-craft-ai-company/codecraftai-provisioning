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


from typing import List, Optional

import yaml

from ccai.provisioning.cloudinit.bootstraprenderer import (
    render_instance_user_data
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
        rendered_hostname: Optional[str] = None
        if instance.vpn_join is not None:
            rendered_hostname = instance.vpn_join.hostname_template.replace(
                "{instance_name}", instance.name
            )

        # The shared composer folds VPN join, Python environments and the
        # raw user_data_script into one document.
        document = render_instance_user_data(
            instance=instance, authkey=authkey,
            rendered_hostname=rendered_hostname,
        )
        rtnval = document if document is not None else ""
        return rtnval
