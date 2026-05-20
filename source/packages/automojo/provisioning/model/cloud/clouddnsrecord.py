"""
    .. module:: clouddnsrecord
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Venue-neutral DNS record descriptor.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import List

from automojo.restclient.base.schemaobject import SchemaObject
from automojo.restclient.base.schemafield import Field

from automojo.provisioning.model.exceptions import SchemaValidationError
from automojo.provisioning.model.cloud.validators import (
    validate_dns_record_type, validate_positive_int
)


class CloudDnsRecord(SchemaObject):
    """
        Venue-neutral DNS record descriptor.

        The supported record types are the documented set (A, AAAA, CNAME, TXT,
        MX, SRV); anything else is rejected at construction.
    """

    zone = Field(str, required=True)
    name = Field(str, required=True)
    record_type = Field(str, required=True)
    values = Field(list, required=True)
    ttl_seconds = Field(int, required=True)

    def __init__(self, *, zone: str, name: str, record_type: str,
                 values: List[str], ttl_seconds: int) -> None:
        """
            Construct a CloudDnsRecord.

            :param zone: DNS zone the record belongs to.
            :param name: Record name within the zone.
            :param record_type: A | AAAA | CNAME | TXT | MX | SRV.
            :param values: List of record value strings.
            :param ttl_seconds: TTL in seconds; must be > 0.

            :raises: SchemaValidationError
        """
        if zone is None or len(zone) == 0:
            raise SchemaValidationError("zone must not be empty.")

        if name is None or len(name) == 0:
            raise SchemaValidationError("name must not be empty.")

        validate_dns_record_type(record_type=record_type)
        validate_positive_int(value=ttl_seconds, field_name="ttl_seconds")

        if values is None or len(values) == 0:
            raise SchemaValidationError("values must not be empty.")

        super().__init__(zone=zone, name=name, record_type=record_type,
                         values=list(values), ttl_seconds=ttl_seconds)
        return
