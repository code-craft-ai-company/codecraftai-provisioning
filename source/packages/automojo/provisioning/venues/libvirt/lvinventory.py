"""
    .. module:: lvinventory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: LvInventory — enumerates run-owned domains for the libvirt
               venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import json
import os

from typing import Any, List

from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.venues.libvirt.lvmetadatatranslator import (
    LvMetadataTranslator
)
from automojo.provisioning.venues.libvirt.lvnaming import run_id_short


_INVENTORY_FILENAME = "libvirt-inventory.json"


class LvInventory:
    """
        Enumerates the libvirt domains owned by a provisioning run.

        Run ownership is decided by the ``automojo-run-id`` element in
        each domain's XML ``<metadata>`` block; the neutral tag list is
        recovered from the same block via :class:`LvMetadataTranslator`.
        IP discovery uses the QEMU guest agent when the interop client
        exposes it; otherwise the IP attribute is left empty.
    """

    def __init__(self, *, client: Any,
                 config: Any = None,
                 output_root: str = ".output",
                 metadata_translator: LvMetadataTranslator = None) -> None:
        """
            Construct an LvInventory.

            :param client: The libvirt interop client.
            :param config: The :class:`LibvirtVenueConfig` (unused
                today, retained for interface uniformity).
            :param output_root: The output root directory.
            :param metadata_translator: Optional
                :class:`LvMetadataTranslator`; defaults to a fresh
                instance.
        """
        self._client = client
        self._config = config
        self._output_root = output_root
        if metadata_translator is not None:
            self._metadata_translator: LvMetadataTranslator = (
                metadata_translator
            )
        else:
            self._metadata_translator = LvMetadataTranslator()
        return

    def list_run(self, *, run_id: str,
                 aspects: Any) -> List[ProvisionedResource]:
        """
            Enumerate every run-id-tagged domain.

            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.

            :returns: A list of :class:`ProvisionedResource` records.
        """
        suffix = "-" + run_id_short(run_id=run_id)

        out: List[ProvisionedResource] = []

        for domain in self._client.domains.list_domains(aspects=aspects):
            domain_xml = self._client.domains.get_domain_xml(
                name=domain.name, aspects=aspects
            )
            embedded_run_id = self._metadata_translator.extract_run_id(
                domain_xml=domain_xml
            )

            if embedded_run_id is not None:
                owned = embedded_run_id == run_id
            else:
                owned = domain.name.endswith(suffix)
            if not owned:
                continue

            tags = self._metadata_translator.extract(
                domain_xml=domain_xml
            )
            ip_address = self._discover_ip(domain_name=domain.name,
                                           aspects=aspects)

            out.append(ProvisionedResource(
                kind="instance", name=domain.name,
                venue_id=domain.uuid,
                attributes={"uuid": domain.uuid,
                            "state": domain.state,
                            "vcpus": domain.vcpus,
                            "memory_kib": domain.memory_kib,
                            "ip": ip_address},
                tags=tags,
            ))

        rtnval = out
        return rtnval

    def _discover_ip(self, *, domain_name: str, aspects: Any) -> str:
        """
            Discover a domain's primary IP via the QEMU guest agent.

            :param domain_name: The venue-side domain name.
            :param aspects: Behaviour control for the interop client.

            :returns: The discovered IP, or an empty string when the
                guest agent is unavailable.
        """
        agent_query = getattr(self._client.domains,
                              "guest_agent_addresses", None)
        if agent_query is None:
            rtnval = ""
            return rtnval

        try:
            addresses = agent_query(name=domain_name, aspects=aspects)
        except Exception:
            rtnval = ""
            return rtnval

        if addresses is not None and len(addresses) > 0:
            rtnval = str(addresses[0])
            return rtnval

        rtnval = ""
        return rtnval

    def persist(self, *, run_id: str,
                resources: List[ProvisionedResource]) -> str:
        """
            Persist an inventory snapshot to the run output directory.

            :param run_id: The provisioning run id.
            :param resources: The resources to persist.

            :returns: The path the inventory snapshot was written to.
        """
        directory = os.path.join(self._output_root, "provisioning", run_id)
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

        path = os.path.join(directory, _INVENTORY_FILENAME)
        document = []
        for resource in resources:
            document.append({
                "kind": resource.kind,
                "name": resource.name,
                "venue_id": resource.venue_id,
                "attributes": dict(resource.attributes),
                "tags": dict(resource.tags),
            })

        with open(path, "w", encoding="utf-8") as fh:
            json.dump(document, fh, indent=2, sort_keys=True)

        rtnval = path
        return rtnval
