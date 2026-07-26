"""
    .. module:: linodereader
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: LinodeReader — tag-filtered read-only lookups against the
               Linode REST client surface.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, List, Optional

from ccai.provisioning.venues.linode.linodetagtranslator import (
    LinodeTagTranslator
)


def _tags_of(*, obj: Any) -> List[str]:
    """
        Return the string-tag list of a Linode SDK object.

        :param obj: A Linode SDK object.

        :returns: A list of string tags (possibly empty).
    """
    tags = getattr(obj, "tags", None)
    if tags is None:
        rtnval: List[str] = []
        return rtnval
    rtnval = list(tags)
    return rtnval


class LinodeReader:
    """
        Read-only lookup helper for the Linode venue.

        Every ``find_*`` method enumerates the matching resource collection
        on the Linode REST client and matches ownership.  Instances,
        firewalls, and volumes carry the venue owner + run-id tags directly.
        VPCs, SSH keys, and Object Storage buckets carry no tags on Linode, so
        they are matched by the venue-scoped label
        ``codecraftai-<run_id>-<name>`` instead.
    """

    def __init__(self, *, client: Any, run_id: str,
                 translator: LinodeTagTranslator) -> None:
        """
            Construct a LinodeReader.

            :param client: A :class:`LinodeRestClient`-compatible object.
            :param run_id: The provisioning run identifier.
            :param translator: A LinodeTagTranslator.
        """
        self._client: Any = client
        self._run_id: str = run_id
        self._translator: LinodeTagTranslator = translator
        return

    def _owned_match(self, *, obj: Any, name: str) -> bool:
        """
            Test whether a Linode object is owned by the run and named.

            :param obj: A Linode SDK object.
            :param name: The neutral resource name to match.

            :returns: True when the object is owned and the name matches.
        """
        tags = _tags_of(obj=obj)
        owned = self._translator.is_owned_by_run(strings=tags,
                                                 run_id=self._run_id)
        if owned is not True:
            rtnval = False
            return rtnval
        resource_name = self._translator.resource_name_of(strings=tags)
        rtnval = resource_name == name
        return rtnval

    def _first_owned(self, *, collection: List[Any],
                     name: str) -> Optional[Any]:
        """
            Return the first owned object in a collection matching a name.

            :param collection: A list of Linode SDK objects.
            :param name: The neutral resource name.

            :returns: The matching object, or None.
        """
        for obj in collection:
            if self._owned_match(obj=obj, name=name):
                rtnval: Optional[Any] = obj
                return rtnval
        rtnval = None
        return rtnval

    def all_owned(self, *, collection: List[Any]) -> List[Any]:
        """
            Return every object in a collection owned by the run.

            :param collection: A list of Linode SDK objects.

            :returns: The owned subset.
        """
        out: List[Any] = []
        for obj in collection:
            tags = _tags_of(obj=obj)
            if self._translator.is_owned_by_run(strings=tags,
                                                run_id=self._run_id):
                out.append(obj)
        rtnval = out
        return rtnval

    def _owned_vpc_prefix(self) -> str:
        """
            Return the venue-scoped label prefix for this run's VPCs.

            :returns: The ``codecraftai-<run_id>-`` prefix string.
        """
        rtnval = "codecraftai-{}-".format(self._run_id)
        return rtnval

    def owned_prefix(self) -> str:
        """
            Return the venue-scoped label prefix for this run.

            Exposed because inventory recovers the neutral name of untagged
            kinds by stripping this prefix from their label.

            :returns: The ``codecraftai-<run_id>-`` prefix string.
        """
        rtnval = self._owned_vpc_prefix()
        return rtnval

    def owned_vpcs(self) -> List[Any]:
        """
            Return every VPC owned by the run, matched by label prefix.

            Linode VPCs carry no tags, so tag-based ``all_owned`` cannot find
            them; ownership is the ``codecraftai-<run_id>-`` label prefix that
            apply assigns.

            :returns: The list of owned VPC SDK objects.
        """
        prefix = self._owned_vpc_prefix()
        out: List[Any] = []
        for vpc in self._client.vpcs():
            vpc_label = getattr(vpc, "label", None)
            if vpc_label is not None and vpc_label.startswith(prefix):
                out.append(vpc)
        rtnval = out
        return rtnval

    def find_vpc(self, *, name: str) -> Optional[Any]:
        """
            Find an owned VPC by name.

            Linode VPCs do not carry tags, so ownership is matched by the
            venue-scoped label ``codecraftai-<run_id>-<name>`` — the same
            convention apply uses when creating them.

            :param name: Neutral network name.

            :returns: The VPC SDK object, or None.
        """
        target_label = "codecraftai-{}-{}".format(self._run_id, name)
        for vpc in self._client.vpcs():
            vpc_label = getattr(vpc, "label", None)
            if vpc_label == target_label:
                rtnval: Optional[Any] = vpc
                return rtnval
        rtnval = None
        return rtnval

    def find_subnet(self, *, name: str) -> Optional[Any]:
        """
            Find an owned VPC subnet by name.

            The search is scoped to this run's owned VPCs so a subnet label
            (which is not run-scoped) cannot collide with another run's VPC.

            :param name: Neutral subnet name.

            :returns: The subnet SDK object, or None.
        """
        for vpc in self.owned_vpcs():
            subnets = getattr(vpc, "subnets", None)
            if subnets is None:
                continue
            for subnet in subnets:
                subnet_label = getattr(subnet, "label", None)
                if subnet_label == name:
                    rtnval: Optional[Any] = subnet
                    return rtnval
        rtnval = None
        return rtnval

    def find_firewall(self, *, name: str) -> Optional[Any]:
        """
            Find an owned Cloud Firewall by name.

            :param name: Neutral security-group name.

            :returns: The firewall SDK object, or None.
        """
        firewalls = list(self._client.networking.firewalls())
        rtnval = self._first_owned(collection=firewalls, name=name)
        return rtnval

    def find_sshkey(self, *, name: str) -> Optional[Any]:
        """
            Find an account SSH key by label.

            SSH keys do not carry tags; they are matched by the venue-scoped
            label ``codecraftai-<run_id>-<name>``.

            :param name: Neutral keypair name.

            :returns: The SSH key SDK object, or None.
        """
        target_label = "codecraftai-{}-{}".format(self._run_id, name)
        for key in self._client.profile.ssh_keys():
            key_label = getattr(key, "label", None)
            if key_label == target_label:
                rtnval: Optional[Any] = key
                return rtnval
        rtnval = None
        return rtnval

    def find_instance(self, *, name: str) -> Optional[Any]:
        """
            Find an owned Linode instance by name.

            :param name: Neutral instance name.

            :returns: The instance SDK object, or None.
        """
        instances = list(self._client.linode.instances())
        rtnval = self._first_owned(collection=instances, name=name)
        return rtnval

    def find_volume(self, *, name: str) -> Optional[Any]:
        """
            Find an owned Block Storage volume by name.

            :param name: Neutral volume name.

            :returns: The volume SDK object, or None.
        """
        volumes = list(self._client.volumes())
        rtnval = self._first_owned(collection=volumes, name=name)
        return rtnval

    def find_bucket(self, *, name: str) -> Optional[Any]:
        """
            Find an Object Storage bucket by label.

            Buckets do not carry tags; they are matched by label.

            :param name: Neutral bucket name.

            :returns: The bucket SDK object, or None.
        """
        for bucket in self._client.object_storage.buckets():
            bucket_label = getattr(bucket, "label", None)
            if bucket_label is None:
                bucket_label = getattr(bucket, "id", None)
            if bucket_label == name:
                rtnval: Optional[Any] = bucket
                return rtnval
        rtnval = None
        return rtnval

    def find_domain(self, *, zone: str) -> Optional[Any]:
        """
            Find a DNS domain by its zone name.

            :param zone: The DNS zone name.

            :returns: The domain SDK object, or None.
        """
        for domain in self._client.domains():
            domain_name = getattr(domain, "domain", None)
            if domain_name == zone:
                rtnval: Optional[Any] = domain
                return rtnval
        rtnval = None
        return rtnval

    def find_dns_record(self, *, zone: str, name: str) -> Optional[Any]:
        """
            Find a DNS record within a zone by record name.

            :param zone: The DNS zone name.
            :param name: The record name.

            :returns: The record SDK object, or None.
        """
        domain = self.find_domain(zone=zone)
        if domain is None:
            rtnval: Optional[Any] = None
            return rtnval
        records = getattr(domain, "records", None)
        if records is None:
            rtnval = None
            return rtnval
        for record in records:
            record_name = getattr(record, "name", None)
            if record_name == name:
                rtnval = record
                return rtnval
        rtnval = None
        return rtnval

    @property
    def run_id(self) -> str:
        """
            Return the run identifier this reader is bound to.

            :returns: The run-id string.
        """
        rtnval = self._run_id
        return rtnval
