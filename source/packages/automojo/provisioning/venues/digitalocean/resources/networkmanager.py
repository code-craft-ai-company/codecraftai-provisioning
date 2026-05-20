"""
    .. module:: networkmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: DigitalOcean VPC manager for the DigitalOcean venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.provisioning.model.cloud.cloudnetwork import CloudNetwork
from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.venues.digitalocean.doclient import (
    DigitalOceanClient
)
from automojo.provisioning.venues.digitalocean.dotagtranslator import (
    base_resource_tags, from_do, to_do, to_flat,
    RESOURCE_NAME_TAG_KEY
)
from automojo.provisioning.venues.digitalocean.doidempotency import (
    matches_name, belongs_to_run
)


class NetworkManager:
    """
        Manager for DigitalOcean VPCs.

        DigitalOcean VPCs are not natively taggable, so the venue owner /
        run / name tag triple is encoded into the VPC ``description`` field
        as a newline-joined ``key=value`` list.  Idempotent ``ensure`` reads
        every region VPC and matches on the encoded run+name tags.
    """

    KIND: str = "network"

    def __init__(self, *, client: DigitalOceanClient) -> None:
        """
            Construct a NetworkManager.

            :param client: DigitalOceanClient.
        """
        self._client: DigitalOceanClient = client
        return

    @staticmethod
    def _encode_description(*, neutral_tags: List[Dict[str, str]]) -> str:
        """
            Encode a neutral tag list into a VPC description string.

            :param neutral_tags: Neutral tag list.

            :returns: A newline-joined ``key=value`` description string.
        """
        rtnval = "\n".join(to_do(neutral_tags=neutral_tags))
        return rtnval

    @staticmethod
    def _decode_description(*, description: Optional[str]
                            ) -> List[Dict[str, str]]:
        """
            Decode a VPC description string back to neutral tags.

            :param description: VPC description string.

            :returns: A neutral tag list.
        """
        if description is None or len(description) == 0:
            rtnval: List[Dict[str, str]] = []
            return rtnval
        rtnval = from_do(do_tags=description.split("\n"))
        return rtnval

    def _all_vpcs(self) -> List[Dict[str, Any]]:
        """
            List every VPC visible to the account.

            :returns: A list of VPC dicts.
        """
        response = self._client.vpcs.list()
        rtnval = list(response.get("vpcs", []))
        return rtnval

    def find(self, *, run_id: str, name: str) -> Optional[Dict[str, Any]]:
        """
            Find an existing owned VPC by run+name tags.

            :param run_id: Run identifier.
            :param name: Neutral network name.

            :returns: The VPC dict, or None.
        """
        for vpc in self._all_vpcs():
            tags = self._decode_description(
                description=vpc.get("description", "")
            )
            do_tags = to_do(neutral_tags=tags)
            if matches_name(do_tags=do_tags, run_id=run_id,
                            resource_name=name):
                rtnval: Optional[Dict[str, Any]] = vpc
                return rtnval
        rtnval = None
        return rtnval

    def matches(self, *, existing: Dict[str, Any],
                desired: CloudNetwork) -> bool:
        """
            Compare an existing VPC to the desired CloudNetwork.

            :param existing: DigitalOcean VPC dict.
            :param desired: Desired CloudNetwork.

            :returns: True when the IP range matches.
        """
        rtnval = existing.get("ip_range", None) == desired.cidr
        return rtnval

    def ensure(self, *, desired: CloudNetwork, run_id: str,
               region: str, default_tags: List[Dict[str, str]],
               aspects: Any) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for a VPC.

            :param desired: Desired CloudNetwork.
            :param run_id: Run identifier (used for owner tagging).
            :param region: DigitalOcean region slug.
            :param default_tags: Venue default tags.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the VPC.
        """
        existing = self.find(run_id=run_id, name=desired.name)
        neutral_tags = base_resource_tags(
            run_id=run_id, resource_name=desired.name,
            resource_kind=self.KIND, extra=list(desired.tags),
            defaults=default_tags,
        )

        if existing is None:
            body: Dict[str, Any] = {
                "name": desired.name,
                "region": region,
                "ip_range": desired.cidr,
                "description": self._encode_description(
                    neutral_tags=neutral_tags
                ),
            }
            created = self._client.vpcs.create(body=body)
            existing = created.get("vpc", {})

        attributes: Dict[str, Any] = {}
        attributes["vpc_id"] = existing.get("id", "")
        attributes["cidr"] = existing.get("ip_range", desired.cidr)
        attributes["region"] = existing.get("region", region)

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name,
            venue_id=str(existing.get("id", "")),
            attributes=attributes, tags=neutral_tags,
        )
        return rtnval

    def destroy(self, *, run_id: str, aspects: Any) -> List[str]:
        """
            Destroy every owned VPC for the run.

            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of destroyed VPC ids.
        """
        deleted: List[str] = []
        for vpc in self._all_vpcs():
            tags = self._decode_description(
                description=vpc.get("description", "")
            )
            do_tags = to_do(neutral_tags=tags)
            if not belongs_to_run(do_tags=do_tags, run_id=run_id):
                continue
            vpc_id = vpc.get("id", "")
            try:
                self._client.vpcs.delete(vpc_id=vpc_id)
                deleted.append(str(vpc_id))
            except Exception:
                pass
        rtnval = deleted
        return rtnval

    def list_owned(self, *, run_id: str) -> List[ProvisionedResource]:
        """
            Return all owned VPCs for the run as ProvisionedResources.

            :param run_id: Run identifier.

            :returns: List of ProvisionedResource entries.
        """
        out: List[ProvisionedResource] = []
        for vpc in self._all_vpcs():
            tags = self._decode_description(
                description=vpc.get("description", "")
            )
            do_tags = to_do(neutral_tags=tags)
            if not belongs_to_run(do_tags=do_tags, run_id=run_id):
                continue
            flat = to_flat(do_tags=do_tags)
            name = flat.get(RESOURCE_NAME_TAG_KEY, "")
            if len(name) == 0:
                continue
            attributes: Dict[str, Any] = {}
            attributes["vpc_id"] = vpc.get("id", "")
            attributes["cidr"] = vpc.get("ip_range", "")
            entry = ProvisionedResource(
                kind=self.KIND, name=name,
                venue_id=str(vpc.get("id", "")),
                attributes=attributes, tags=tags,
            )
            out.append(entry)
        rtnval = out
        return rtnval
