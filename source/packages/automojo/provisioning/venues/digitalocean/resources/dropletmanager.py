"""
    .. module:: dropletmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: DigitalOcean Droplet manager for the DigitalOcean venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional, Tuple

from automojo.provisioning.model.cloud.cloudinstance import CloudInstance
from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.venues.digitalocean.doclient import (
    DigitalOceanClient
)
from automojo.provisioning.venues.digitalocean.doidempotency import (
    matches_name, belongs_to_run, run_tag_string
)
from automojo.provisioning.venues.digitalocean.doresolver import DoResolver
from automojo.provisioning.venues.digitalocean.dotagtranslator import (
    base_resource_tags, from_do, to_do, to_flat, RESOURCE_NAME_TAG_KEY
)
from automojo.provisioning.venues.digitalocean.douserdatarenderer import (
    DoUserDataRenderer
)


def _public_ipv4(*, droplet: Dict[str, Any]) -> str:
    """
        Extract the public IPv4 address from a Droplet dict.

        :param droplet: DigitalOcean Droplet dict.

        :returns: The public IPv4 string, or empty.
    """
    networks = droplet.get("networks", {}) or {}
    for entry in networks.get("v4", []) or []:
        if entry.get("type", "") == "public":
            rtnval = entry.get("ip_address", "")
            return rtnval
    rtnval = ""
    return rtnval


def _private_ipv4(*, droplet: Dict[str, Any]) -> str:
    """
        Extract the private (VPC) IPv4 address from a Droplet dict.

        :param droplet: DigitalOcean Droplet dict.

        :returns: The private IPv4 string, or empty.
    """
    networks = droplet.get("networks", {}) or {}
    for entry in networks.get("v4", []) or []:
        if entry.get("type", "") == "private":
            rtnval = entry.get("ip_address", "")
            return rtnval
    rtnval = ""
    return rtnval


class DropletManager:
    """
        Manager for DigitalOcean Droplets.

        Droplets carry the venue owner / run / name tags natively.  A
        ``vpn_join`` spec is rendered to cloud-init and passed as
        ``user_data``.  Size changes are UPDATE-by-recreate and are gated on
        ``aspects.confirm``.
    """

    KIND: str = "instance"

    def __init__(self, *, client: DigitalOceanClient,
                 resolver: DoResolver,
                 user_data_renderer: DoUserDataRenderer) -> None:
        """
            Construct a DropletManager.

            :param client: DigitalOceanClient.
            :param resolver: DoResolver for image / size slugs.
            :param user_data_renderer: DoUserDataRenderer.
        """
        self._client: DigitalOceanClient = client
        self._resolver: DoResolver = resolver
        self._user_data_renderer: DoUserDataRenderer = user_data_renderer
        return

    def _run_droplets(self, *, run_id: str) -> List[Dict[str, Any]]:
        """
            List every Droplet tagged with the run-id.

            :param run_id: Run identifier.

            :returns: A list of Droplet dicts.
        """
        response = self._client.droplets.list(
            tag_name=run_tag_string(run_id=run_id)
        )
        rtnval = list(response.get("droplets", []))
        return rtnval

    def find(self, *, run_id: str, name: str) -> Optional[Dict[str, Any]]:
        """
            Find an existing owned Droplet by run+name tags.

            :param run_id: Run identifier.
            :param name: Neutral instance name.

            :returns: The Droplet dict, or None.
        """
        for droplet in self._run_droplets(run_id=run_id):
            do_tags = droplet.get("tags", [])
            if matches_name(do_tags=do_tags, run_id=run_id,
                            resource_name=name):
                rtnval: Optional[Dict[str, Any]] = droplet
                return rtnval
        rtnval = None
        return rtnval

    def matches(self, *, existing: Dict[str, Any],
                desired: CloudInstance) -> bool:
        """
            Compare an existing Droplet to the desired CloudInstance.

            :param existing: DigitalOcean Droplet dict.
            :param desired: Desired CloudInstance.

            :returns: True when the size slug matches.
        """
        size_slug = self._resolver.size_to_slug(
            size_hint=desired.size, accelerators=desired.accelerators
        )
        existing_size = existing.get("size_slug", "")
        if len(existing_size) == 0:
            existing_size = (existing.get("size", {}) or {}).get("slug", "")
        rtnval = existing_size == size_slug
        return rtnval

    def ensure(self, *, desired: CloudInstance, run_id: str,
               region: str, vpc_uuid: str, ssh_key_ids: List[Any],
               default_tags: List[Dict[str, str]],
               authkey: Optional[str] = None,
               aspects: Any = None) -> Tuple[ProvisionedResource,
                                             Dict[str, Any]]:
        """
            Match-then-act create-or-reuse for a Droplet.

            :param desired: Desired CloudInstance.
            :param run_id: Run identifier.
            :param region: DigitalOcean region slug.
            :param vpc_uuid: Optional parent VPC uuid (empty for default).
            :param ssh_key_ids: SSH key ids / fingerprints to inject.
            :param default_tags: Venue default tags.
            :param authkey: Optional minted VPN auth key.
            :param aspects: Aspects.

            :returns: A tuple of (ProvisionedResource, info-dict).
        """
        existing = self.find(run_id=run_id, name=desired.name)
        neutral_tags = base_resource_tags(
            run_id=run_id, resource_name=desired.name,
            resource_kind=self.KIND, extra=list(desired.tags),
            defaults=default_tags,
        )
        do_tags = to_do(neutral_tags=neutral_tags)

        user_data = self._user_data_renderer.render(
            instance=desired, authkey=authkey
        )
        info: Dict[str, Any] = {}
        info["user_data_body"] = user_data
        info["vpn_device_id"] = None

        if existing is None:
            image_slug = self._resolver.image_to_slug(
                family=desired.image.family,
                version=desired.image.version,
                architecture=desired.image.architecture,
            )
            size_slug = self._resolver.size_to_slug(
                size_hint=desired.size, accelerators=desired.accelerators
            )
            body: Dict[str, Any] = {
                "name": desired.name,
                "region": region,
                "size": size_slug,
                "image": image_slug,
                "tags": do_tags,
                "ssh_keys": list(ssh_key_ids),
            }
            if len(user_data) > 0:
                body["user_data"] = user_data
            if vpc_uuid is not None and len(vpc_uuid) > 0:
                body["vpc_uuid"] = vpc_uuid
            created = self._client.droplets.create(body=body)
            existing = created.get("droplet", {})

        size_slug = existing.get("size_slug", "")
        if len(size_slug) == 0:
            size_slug = (existing.get("size", {}) or {}).get("slug", "")

        attributes: Dict[str, Any] = {}
        attributes["droplet_id"] = existing.get("id", "")
        attributes["size_slug"] = size_slug
        attributes["public_ip"] = _public_ipv4(droplet=existing)
        attributes["private_ip"] = _private_ipv4(droplet=existing)
        if len(user_data) > 0:
            attributes["user_data_present"] = True

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name,
            venue_id=str(existing.get("id", "")),
            attributes=attributes, tags=neutral_tags,
        )
        return rtnval, info

    def destroy(self, *, run_id: str,
                aspects: Any) -> List[Dict[str, Any]]:
        """
            Destroy every owned Droplet for the run.

            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: A list of records describing destroyed Droplets.
        """
        destroyed: List[Dict[str, Any]] = []
        for droplet in self._run_droplets(run_id=run_id):
            do_tags = droplet.get("tags", [])
            if not belongs_to_run(do_tags=do_tags, run_id=run_id):
                continue
            droplet_id = droplet.get("id", "")
            flat = to_flat(do_tags=do_tags)
            try:
                self._client.droplets.destroy(droplet_id=droplet_id)
                destroyed.append({
                    "droplet_id": droplet_id,
                    "instance_name": flat.get(RESOURCE_NAME_TAG_KEY, ""),
                    "vpn_device_id": None,
                })
            except Exception:
                pass
        rtnval = destroyed
        return rtnval

    def list_owned(self, *, run_id: str) -> List[ProvisionedResource]:
        """
            Return all owned Droplets for the run as ProvisionedResources.

            :param run_id: Run identifier.

            :returns: List of ProvisionedResource entries.
        """
        out: List[ProvisionedResource] = []
        for droplet in self._run_droplets(run_id=run_id):
            do_tags = droplet.get("tags", [])
            if not belongs_to_run(do_tags=do_tags, run_id=run_id):
                continue
            flat = to_flat(do_tags=do_tags)
            name = flat.get(RESOURCE_NAME_TAG_KEY, "")
            if len(name) == 0:
                continue
            size_slug = droplet.get("size_slug", "")
            if len(size_slug) == 0:
                size_slug = (droplet.get("size", {}) or {}).get("slug", "")
            attributes: Dict[str, Any] = {}
            attributes["droplet_id"] = droplet.get("id", "")
            attributes["size_slug"] = size_slug
            attributes["public_ip"] = _public_ipv4(droplet=droplet)
            attributes["private_ip"] = _private_ipv4(droplet=droplet)
            entry = ProvisionedResource(
                kind=self.KIND, name=name,
                venue_id=str(droplet.get("id", "")),
                attributes=attributes, tags=from_do(do_tags=do_tags),
            )
            out.append(entry)
        rtnval = out
        return rtnval
