"""
    .. module:: dnsmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: DigitalOcean DNS record manager for the DigitalOcean venue.

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
from automojo.provisioning.venues.digitalocean.doclient import (
    DigitalOceanClient
)
from automojo.provisioning.venues.digitalocean.doerrors import (
    DoValidationError
)


class DnsManager:
    """
        Manager for DigitalOcean DNS records.

        DigitalOcean DNS records hang off an existing domain; the domain
        must already exist on the account.  Records are matched by
        (name, type) within the domain so re-applying is idempotent.
    """

    KIND: str = "dns"

    def __init__(self, *, client: DigitalOceanClient) -> None:
        """
            Construct a DnsManager.

            :param client: DigitalOceanClient.
        """
        self._client: DigitalOceanClient = client
        return

    def _existing_record(self, *, zone: str, name: str,
                         record_type: str) -> Optional[Dict[str, Any]]:
        """
            Find an existing record matching (name, type) within the zone.

            :param zone: The DNS domain name.
            :param name: The record name.
            :param record_type: The DNS record type.

            :returns: The record dict, or None.
        """
        response = self._client.domains.list_records(domain_name=zone)
        for record in response.get("domain_records", []):
            if record.get("name", "") == name and record.get("type", "") == record_type:
                rtnval: Optional[Dict[str, Any]] = record
                return rtnval
        rtnval = None
        return rtnval

    def ensure(self, *, desired: CloudDnsRecord, run_id: str,
               aspects: Any = None) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for a DNS record.

            :param desired: Desired CloudDnsRecord.
            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the record.
            :raises: DoValidationError
        """
        values = desired.values if desired.values is not None else []
        if len(values) == 0:
            err_msg_lines = ["DNS record requires at least one value."]
            err_msg_lines.append("RECORD: {}".format(desired.name))
            err_msg = os.linesep.join(err_msg_lines)
            raise DoValidationError(err_msg)

        first_value = values[0]
        existing = self._existing_record(
            zone=desired.zone, name=desired.name,
            record_type=desired.record_type,
        )

        if existing is None:
            body: Dict[str, Any] = {
                "type": desired.record_type,
                "name": desired.name,
                "data": first_value,
                "ttl": desired.ttl_seconds,
            }
            created = self._client.domains.create_record(
                domain_name=desired.zone, body=body
            )
            existing = created.get("domain_record", {})

        attributes: Dict[str, Any] = {}
        attributes["record_id"] = existing.get("id", "")
        attributes["zone"] = desired.zone
        attributes["record_type"] = desired.record_type

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name,
            venue_id=str(existing.get("id", "")),
            attributes=attributes, tags=[],
        )
        return rtnval

    def destroy_record(self, *, desired: CloudDnsRecord,
                       aspects: Any) -> None:
        """
            Delete a DNS record created by the venue.

            :param desired: The CloudDnsRecord to remove.
            :param aspects: Aspects.
        """
        existing = self._existing_record(
            zone=desired.zone, name=desired.name,
            record_type=desired.record_type,
        )
        if existing is None:
            return
        try:
            self._client.domains.delete_record(
                domain_name=desired.zone,
                domain_record_id=existing.get("id", ""),
            )
        except Exception:
            pass
        return

    def list_owned(self, *, dns_records: List[CloudDnsRecord]
                   ) -> List[ProvisionedResource]:
        """
            Return DNS records present for the run as ProvisionedResources.

            :param dns_records: The CloudDnsRecord list from the run's spec.

            :returns: List of ProvisionedResource entries.
        """
        out: List[ProvisionedResource] = []
        for desired in dns_records:
            existing = self._existing_record(
                zone=desired.zone, name=desired.name,
                record_type=desired.record_type,
            )
            if existing is None:
                continue
            attributes: Dict[str, Any] = {}
            attributes["record_id"] = existing.get("id", "")
            attributes["zone"] = desired.zone
            attributes["record_type"] = desired.record_type
            entry = ProvisionedResource(
                kind=self.KIND, name=desired.name,
                venue_id=str(existing.get("id", "")),
                attributes=attributes, tags=[],
            )
            out.append(entry)
        rtnval = out
        return rtnval
