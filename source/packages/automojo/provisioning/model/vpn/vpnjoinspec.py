"""
    .. module:: vpnjoinspec
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Declarative VPN join specification attached to a CloudInstance.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import List, Optional

from automojo.restclient.base.schemaobject import SchemaObject
from automojo.restclient.base.schemafield import Field

from automojo.provisioning.model.exceptions import SchemaValidationError
from automojo.provisioning.model.cloud.validators import validate_cidr


_SUPPORTED_PROVIDERS = ("tailscale", "twingate")


class VPNJoinSpec(SchemaObject):
    """
        Declarative VPN join specification.

        Carries everything a venue provisioner needs to inject VPN install +
        bring-up commands into the bootstrap payload.  Auth-key material is
        never stored on this object — the lifecycle layer mints an ephemeral
        key just-in-time.
    """

    provider = Field(str, required=True)
    control_plane_credential = Field(str, required=True)
    advertise_tags = Field(list, required=False, default=None)
    hostname_template = Field(str, required=True)
    ephemeral = Field(bool, required=False, default=True)
    preauthorized = Field(bool, required=False, default=True)
    advertise_routes = Field(list, required=False, default=None)
    exit_node = Field(bool, required=False, default=False)
    connector_only = Field(bool, required=False, default=False)

    def __init__(self, *, provider: str, control_plane_credential: str,
                 hostname_template: str,
                 advertise_tags: Optional[List[str]] = None,
                 ephemeral: bool = True,
                 preauthorized: bool = True,
                 advertise_routes: Optional[List[str]] = None,
                 exit_node: bool = False,
                 connector_only: bool = False) -> None:
        """
            Construct a VPNJoinSpec.

            :param provider: One of tailscale or twingate.
            :param control_plane_credential: Credential vault name.
            :param hostname_template: Template rendered per-instance.
            :param advertise_tags: Optional list of advertised tags.
            :param ephemeral: Whether the minted auth-key is ephemeral.
            :param preauthorized: Whether the minted auth-key is preauthorized.
            :param advertise_routes: Optional list of advertised CIDRs.
            :param exit_node: Whether to advertise as an exit node.
            :param connector_only: Required True for Twingate connectors.

            :raises: SchemaValidationError
        """
        if provider not in _SUPPORTED_PROVIDERS:
            raise SchemaValidationError(
                "provider must be one of {}, got {!r}".format(
                    ", ".join(_SUPPORTED_PROVIDERS), provider
                )
            )

        if control_plane_credential is None or len(control_plane_credential) == 0:
            raise SchemaValidationError(
                "control_plane_credential must not be empty."
            )

        if hostname_template is None or len(hostname_template) == 0:
            raise SchemaValidationError(
                "hostname_template must not be empty."
            )

        effective_tags = advertise_tags if advertise_tags is not None else []
        effective_routes = advertise_routes if advertise_routes is not None else []

        for cidr in effective_routes:
            validate_cidr(value=cidr)

        if provider == "twingate":
            if exit_node:
                raise SchemaValidationError(
                    "Twingate does not support exit_node mode."
                )
            if not connector_only:
                raise SchemaValidationError(
                    "Twingate requires connector_only=True."
                )

        super().__init__(provider=provider,
                         control_plane_credential=control_plane_credential,
                         hostname_template=hostname_template,
                         advertise_tags=effective_tags,
                         ephemeral=ephemeral, preauthorized=preauthorized,
                         advertise_routes=effective_routes,
                         exit_node=exit_node, connector_only=connector_only)
        return
