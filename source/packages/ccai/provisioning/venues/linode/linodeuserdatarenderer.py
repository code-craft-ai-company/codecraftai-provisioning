"""
    .. module:: linodeuserdatarenderer
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: LinodeUserDataRenderer — renders a VPNJoinSpec into the
               base64 ``metadata.user_data`` payload for a Linode instance.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import base64

from typing import Optional

import yaml

from ccai.provisioning.cloudinit.bootstraprenderer import (
    render_instance_user_data
)
from ccai.provisioning.cloudinit.vpncloudinitrenderer import (
    render_cloud_init
)
from ccai.provisioning.model.cloud.cloudinstance import CloudInstance
from ccai.interfaces.vpnjoinspec import VPNJoinSpec


class LinodeUserDataRenderer:
    """
        Renderer that produces the ``metadata.user_data`` field of a Linode
        instance create call.

        Linode instances accept a base64-encoded cloud-config document via
        the Metadata service.  The renderer composes the VPN-join cloud-init
        fragment from the M6 renderer and base64-encodes the result.
    """

    def render(self, *, spec: VPNJoinSpec, authkey: str,
               rendered_hostname: str, image_family: str) -> str:
        """
            Render the base64 ``metadata.user_data`` payload.

            :param spec: The VPNJoinSpec carried by the instance.
            :param authkey: Minted auth key (Tailscale) or connector token.
            :param rendered_hostname: Hostname computed from the host
                                      template.
            :param image_family: Image family (``ubuntu``, ``debian``...).

            :returns: A base64-encoded cloud-config string.
            :raises: CloudInitRendererError
        """
        fragment = render_cloud_init(
            spec=spec, authkey=authkey,
            rendered_hostname=rendered_hostname,
            image_family=image_family,
        )
        document = "#cloud-config\n" + yaml.safe_dump(fragment,
                                                      default_flow_style=False)
        encoded_bytes = base64.b64encode(document.encode("utf-8"))
        rtnval = encoded_bytes.decode("ascii")
        return rtnval

    def render_instance(self, *, instance: CloudInstance,
                        authkey: Optional[str] = None,
                        rendered_hostname: Optional[str] = None
                        ) -> Optional[str]:
        """
            Render the base64 ``metadata.user_data`` payload for an instance
            from every bootstrap slot it declares (VPN join, Python
            environments, raw user-data script) via the shared composer.

            :param instance: The neutral CloudInstance.
            :param authkey: Minted auth key when ``vpn_join`` is set.
            :param rendered_hostname: Hostname computed from the host
                                      template (defaults to the name).

            :returns: A base64-encoded string, or None when the instance
                      needs no launch metadata.
            :raises: CloudInitRendererError
        """
        document = render_instance_user_data(
            instance=instance, authkey=authkey,
            rendered_hostname=rendered_hostname,
        )
        if document is None:
            rtnval: Optional[str] = None
            return rtnval

        encoded_bytes = base64.b64encode(document.encode("utf-8"))
        rtnval = encoded_bytes.decode("ascii")
        return rtnval

    def render_raw(self, *, user_data_script: Optional[str]) -> Optional[str]:
        """
            Render a raw user-data script as a base64 payload.

            :param user_data_script: A raw user-data script, or None.

            :returns: A base64-encoded string, or None when no script was
                      supplied.
        """
        if user_data_script is None or len(user_data_script) == 0:
            rtnval: Optional[str] = None
            return rtnval

        encoded_bytes = base64.b64encode(user_data_script.encode("utf-8"))
        rtnval = encoded_bytes.decode("ascii")
        return rtnval
