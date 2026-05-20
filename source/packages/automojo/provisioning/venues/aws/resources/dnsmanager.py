"""
    .. module:: dnsmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: AWS Route53 DNS record manager for the AWS venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Any, Dict, List, Optional

from automojo.provisioning.model.cloud.clouddnsrecord import CloudDnsRecord
from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.venues.aws.awsboto3sessionfactory import (
    AwsBoto3SessionFactory
)
from automojo.provisioning.venues.aws.awserrors import AwsValidationError


class DnsManager:
    """
        Manager for Route53 record sets.

        The hosted zone is looked up by ``zone_name`` (the spec's ``zone``
        field).  Records are upserted via ``change_resource_record_sets``.
    """

    KIND: str = "dns"

    def __init__(self, *, session_factory: AwsBoto3SessionFactory) -> None:
        """
            Construct a DnsManager.

            :param session_factory: AwsBoto3SessionFactory.
        """
        self._session_factory: AwsBoto3SessionFactory = session_factory
        return

    def _r53(self) -> Any:
        rtnval = self._session_factory.client(service_name="route53")
        return rtnval

    def _zone_id(self, *, zone_name: str) -> str:
        """
            Look up a hosted zone id by name.

            :param zone_name: DNS zone name (with or without trailing dot).

            :returns: The hosted zone id (without ``/hostedzone/`` prefix).
            :raises: AwsValidationError
        """
        target = zone_name if zone_name.endswith(".") else zone_name + "."
        client = self._r53()
        response = client.list_hosted_zones()
        for zone in response.get("HostedZones", []):
            if zone.get("Name", "") == target:
                zid = zone.get("Id", "")
                if zid.startswith("/hostedzone/"):
                    rtnval = zid[len("/hostedzone/"):]
                    return rtnval
                rtnval = zid
                return rtnval

        err_msg_lines = ["Route53 hosted zone not found for record."]
        err_msg_lines.append("ZONE: {}".format(zone_name))
        err_msg = os.linesep.join(err_msg_lines)
        raise AwsValidationError(err_msg)

    def ensure(self, *, desired: CloudDnsRecord, run_id: str,
               aspects: Any) -> ProvisionedResource:
        """
            Upsert a Route53 record.

            :param desired: Desired CloudDnsRecord.
            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the record.
        """
        zone_id = self._zone_id(zone_name=desired.zone)
        client = self._r53()
        change = {
            "Action": "UPSERT",
            "ResourceRecordSet": {
                "Name": desired.name,
                "Type": desired.record_type,
                "TTL": desired.ttl_seconds,
                "ResourceRecords": [{"Value": v} for v in desired.values],
            },
        }
        client.change_resource_record_sets(
            HostedZoneId=zone_id,
            ChangeBatch={"Changes": [change]},
        )

        attributes: Dict[str, Any] = {}
        attributes["zone_id"] = zone_id
        attributes["record_type"] = desired.record_type
        attributes["values"] = list(desired.values)
        attributes["ttl_seconds"] = desired.ttl_seconds

        venue_id = "{}#{}#{}".format(zone_id, desired.name,
                                     desired.record_type)
        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name, venue_id=venue_id,
            attributes=attributes, tags=[],
        )
        return rtnval

    def destroy_record(self, *, desired: CloudDnsRecord,
                       aspects: Any) -> None:
        """
            Delete a Route53 record set.

            :param desired: The CloudDnsRecord that was previously upserted.
            :param aspects: Aspects.
        """
        try:
            zone_id = self._zone_id(zone_name=desired.zone)
        except AwsValidationError:
            return

        client = self._r53()
        change = {
            "Action": "DELETE",
            "ResourceRecordSet": {
                "Name": desired.name,
                "Type": desired.record_type,
                "TTL": desired.ttl_seconds,
                "ResourceRecords": [{"Value": v} for v in desired.values],
            },
        }
        try:
            client.change_resource_record_sets(
                HostedZoneId=zone_id,
                ChangeBatch={"Changes": [change]},
            )
        except Exception:
            return
        return
