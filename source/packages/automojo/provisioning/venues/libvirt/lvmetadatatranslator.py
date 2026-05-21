"""
    .. module:: lvmetadatatranslator
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: LvMetadataTranslator — neutral tags <-> libvirt XML metadata.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import xml.etree.ElementTree as ElementTree

from typing import Dict, List, Optional


# The custom namespace under which the provisioner records the run id and
# neutral tag list.  libvirt has no native tag concept, so a metadata
# block under this namespace is the only stable ownership signal.
AUTOMOJO_NAMESPACE = "https://automationmojo.com/provisioning/v1"


class LvMetadataTranslator:
    """
        Translate between the neutral tag form (a flat ``{key: value}``
        dict) and a libvirt ``<metadata>`` inner-XML fragment.

        For conformant inputs — non-empty string keys / values — the round
        trip ``extract(embed(tags, run_id))`` recovers the neutral tag dict
        as the identity.  Keys / values containing namespaces, colons,
        and whitespace round-trip because the values are carried in
        element text, which the XML serialiser escapes / unescapes.
    """

    def embed(self, *, neutral_tags: Optional[Dict[str, str]],
              run_id: str) -> str:
        """
            Render the inner XML of a ``<metadata>`` block.

            The returned string is the inner XML — the
            ``<automojo:metadata>`` element and its children — suitable
            for the interop ``LibvirtDomainSpec.metadata_xml`` field.

            :param neutral_tags: A flat ``{key: value}`` dict of tag pairs,
                or ``None``.
            :param run_id: The provisioning run id.

            :returns: The metadata inner-XML fragment string.
        """
        root = ElementTree.Element("{%s}metadata" % AUTOMOJO_NAMESPACE)

        run_element = ElementTree.SubElement(
            root, "{%s}run-id" % AUTOMOJO_NAMESPACE
        )
        run_element.text = run_id

        tags_element = ElementTree.SubElement(
            root, "{%s}tags" % AUTOMOJO_NAMESPACE
        )

        effective_tags: Dict[str, str] = {}
        if neutral_tags is not None:
            effective_tags = neutral_tags

        for key, value in effective_tags.items():
            tag_element = ElementTree.SubElement(
                tags_element, "{%s}tag" % AUTOMOJO_NAMESPACE
            )
            tag_element.set("key", key)
            tag_element.text = value

        ElementTree.register_namespace("automojo", AUTOMOJO_NAMESPACE)
        rtnval = ElementTree.tostring(root, encoding="unicode")
        return rtnval

    def extract_run_id(self, *, domain_xml: str) -> Optional[str]:
        """
            Recover the run id embedded in a domain's XML, if any.

            :param domain_xml: The full domain XML string.

            :returns: The recovered run id, or ``None`` when the domain
                carries no automojo metadata.
        """
        run_element = self._find_run_element(domain_xml=domain_xml)
        if run_element is None:
            rtnval: Optional[str] = None
            return rtnval

        rtnval = run_element.text
        return rtnval

    def extract(self, *, domain_xml: str) -> Dict[str, str]:
        """
            Recover the neutral tag dict embedded in a domain's XML.

            :param domain_xml: The full domain XML string.

            :returns: The neutral flat tag dict, or an empty dict when the
                domain carries no automojo tags.
        """
        out: Dict[str, str] = {}

        try:
            root = ElementTree.fromstring(domain_xml)
        except ElementTree.ParseError:
            rtnval = out
            return rtnval

        tags_element = root.find(
            ".//{%s}tags" % AUTOMOJO_NAMESPACE
        )
        if tags_element is None:
            rtnval = out
            return rtnval

        for tag_element in tags_element.findall(
            "{%s}tag" % AUTOMOJO_NAMESPACE
        ):
            key = tag_element.get("key", None)
            if key is None:
                continue
            value = tag_element.text
            if value is None:
                value = ""
            out[key] = value

        rtnval = out
        return rtnval

    def _find_run_element(self, *, domain_xml: str
                          ) -> Optional[ElementTree.Element]:
        """
            Locate the ``run-id`` element within a domain XML document.

            :param domain_xml: The full domain XML string.

            :returns: The run-id element, or ``None`` when absent.
        """
        try:
            root = ElementTree.fromstring(domain_xml)
        except ElementTree.ParseError:
            rtnval: Optional[ElementTree.Element] = None
            return rtnval

        rtnval = root.find(".//{%s}run-id" % AUTOMOJO_NAMESPACE)
        return rtnval
