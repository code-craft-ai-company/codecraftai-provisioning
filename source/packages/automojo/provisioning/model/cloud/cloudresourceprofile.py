"""
    .. module:: cloudresourceprofile
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Typed-kind CloudResourceProfile dispatcher.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Any, Dict, List, Optional, Type, Union

from automojo.restclient.base.schemaobject import SchemaObject
from automojo.restclient.base.schemafield import Field

from automojo.provisioning.model.exceptions import SchemaValidationError
from automojo.provisioning.model.cloud.cloudresourcekind import CloudResourceKind
from automojo.provisioning.model.cloud.cloudnetwork import CloudNetwork
from automojo.provisioning.model.cloud.cloudsubnet import CloudSubnet
from automojo.provisioning.model.cloud.cloudsecuritygroup import CloudSecurityGroup
from automojo.provisioning.model.cloud.cloudkeypair import CloudKeyPair
from automojo.provisioning.model.cloud.cloudimage import CloudImage
from automojo.provisioning.model.cloud.cloudinstance import CloudInstance
from automojo.provisioning.model.cloud.cloudstoragevolume import CloudStorageVolume
from automojo.provisioning.model.cloud.cloudobjectbucket import CloudObjectBucket
from automojo.provisioning.model.cloud.cloudloadbalancer import CloudLoadBalancer
from automojo.provisioning.model.cloud.clouddnsrecord import CloudDnsRecord


_KIND_TO_CLASS: Dict[CloudResourceKind, Type[SchemaObject]] = {
    CloudResourceKind.NETWORK: CloudNetwork,
    CloudResourceKind.SUBNET: CloudSubnet,
    CloudResourceKind.SECURITY_GROUP: CloudSecurityGroup,
    CloudResourceKind.KEYPAIR: CloudKeyPair,
    CloudResourceKind.IMAGE: CloudImage,
    CloudResourceKind.INSTANCE: CloudInstance,
    CloudResourceKind.VOLUME: CloudStorageVolume,
    CloudResourceKind.BUCKET: CloudObjectBucket,
    CloudResourceKind.LOAD_BALANCER: CloudLoadBalancer,
    CloudResourceKind.DNS_RECORD: CloudDnsRecord,
}


def resolve_kind(*, value: Union[CloudResourceKind, str]) -> CloudResourceKind:
    """
        Resolve a string or enum value to a CloudResourceKind.

        :param value: The kind value.

        :returns: The CloudResourceKind.
        :raises: SchemaValidationError
    """
    if isinstance(value, CloudResourceKind):
        rtnval = value
        return rtnval

    if not isinstance(value, str):
        raise SchemaValidationError(
            "kind must be a CloudResourceKind or string."
        )

    try:
        rtnval = CloudResourceKind(value)
    except ValueError:
        supported = ", ".join(k.value for k in CloudResourceKind)
        err_msg_lines = ["Unsupported CloudResourceProfile kind."]
        err_msg_lines.append("SUPPORTED: {}".format(supported))
        err_msg_lines.append("ACTUAL: {!r}".format(value))
        err_msg = os.linesep.join(err_msg_lines)
        raise SchemaValidationError(err_msg) from None

    return rtnval


def model_class_for_kind(*, kind: CloudResourceKind) -> Type[SchemaObject]:
    """
        Return the SchemaObject subclass that backs the given kind.

        :param kind: The CloudResourceKind enum value.

        :returns: The matching SchemaObject subclass.
    """
    rtnval = _KIND_TO_CLASS[kind]
    return rtnval


class CloudResourceProfile(SchemaObject):
    """
        Typed-kind resource profile descriptor.

        Carries metadata (name, description, credential, tags) plus a typed
        ``kind`` discriminator and a payload dict that is shape-validated
        against the matching model class.
    """

    name = Field(str, required=True)
    kind = Field(str, required=True)
    description = Field(str, required=False, default="")
    credential = Field(str, required=False, default=None)
    payload = Field(dict, required=False, default=None)
    tags = Field(list, required=False, default=None)

    def __init__(self, *, name: str,
                 kind: Union[CloudResourceKind, str],
                 description: str = "",
                 credential: Optional[str] = None,
                 payload: Optional[Dict[str, Any]] = None,
                 tags: Optional[List[Dict[str, str]]] = None) -> None:
        """
            Construct a CloudResourceProfile.

            :param name: Profile name.
            :param kind: One of the CloudResourceKind values.
            :param description: Optional human description.
            :param credential: Optional credential vault reference name.
            :param payload: Optional payload validated against the matching
                            model class.
            :param tags: Optional list of single-entry tag dicts.

            :raises: SchemaValidationError
        """
        if name is None or len(name) == 0:
            raise SchemaValidationError("name must not be empty.")

        resolved_kind = resolve_kind(value=kind)

        effective_payload = payload if payload is not None else {}
        effective_tags = tags if tags is not None else []

        if len(effective_payload) > 0:
            target_cls = model_class_for_kind(kind=resolved_kind)
            try:
                target_cls.from_dict(effective_payload)
            except SchemaValidationError:
                raise
            except Exception as xcpt:
                err_msg_lines = [
                    "Payload failed shape validation for resource kind."
                ]
                err_msg_lines.append("KIND: {}".format(resolved_kind.value))
                err_msg_lines.append("CAUSE: {}".format(xcpt))
                err_msg = os.linesep.join(err_msg_lines)
                raise SchemaValidationError(err_msg) from None

        super().__init__(name=name, kind=resolved_kind.value,
                         description=description, credential=credential,
                         payload=effective_payload, tags=effective_tags)
        return

    def dispatch(self) -> SchemaObject:
        """
            Construct and return the typed model instance for this profile.

            :returns: A model instance matching this profile's kind.
        """
        resolved_kind = resolve_kind(value=self.kind)
        target_cls = model_class_for_kind(kind=resolved_kind)
        rtnval = target_cls.from_dict(self.payload)
        return rtnval
