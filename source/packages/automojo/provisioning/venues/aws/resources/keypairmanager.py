"""
    .. module:: keypairmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: AWS EC2 KeyPair manager for the AWS venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.provisioning.model.cloud.cloudkeypair import CloudKeyPair
from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.venues.aws.awsboto3sessionfactory import (
    AwsBoto3SessionFactory
)
from automojo.provisioning.venues.aws.awsidempotency import (
    owner_filters, tag_dict_from_aws
)
from automojo.provisioning.venues.aws.awstagging import (
    base_resource_tags, tag_specifications, from_aws, RESOURCE_NAME_TAG_KEY
)


class KeyPairManager:
    """
        Manager for imported EC2 KeyPairs.

        The public key material from the neutral CloudKeyPair is imported
        via ``import_key_pair``.  AWS key-pair names are run-scoped so
        re-runs don't collide.
    """

    KIND: str = "keypair"

    def __init__(self, *, session_factory: AwsBoto3SessionFactory) -> None:
        """
            Construct a KeyPairManager.

            :param session_factory: AwsBoto3SessionFactory.
        """
        self._session_factory: AwsBoto3SessionFactory = session_factory
        return

    def _ec2(self) -> Any:
        rtnval = self._session_factory.client(service_name="ec2")
        return rtnval

    def _aws_keyname(self, *, run_id: str, name: str) -> str:
        """
            Build the AWS key-pair name (run-scoped).

            :param run_id: Run identifier.
            :param name: Neutral key pair name.

            :returns: The AWS-side key pair name.
        """
        rtnval = "automojo-{}-{}".format(run_id, name)
        return rtnval

    def find(self, *, run_id: str, name: str) -> Optional[Dict[str, Any]]:
        """
            Find an existing owned KeyPair by run+name tags.

            :param run_id: Run identifier.
            :param name: Neutral key pair name.

            :returns: The describe_key_pairs entry or None.
        """
        client = self._ec2()
        filters = owner_filters(run_id=run_id, resource_name=name)
        try:
            response = client.describe_key_pairs(Filters=filters)
        except Exception:
            rtnval: Optional[Dict[str, Any]] = None
            return rtnval
        pairs = response.get("KeyPairs", [])
        if len(pairs) == 0:
            rtnval = None
            return rtnval
        rtnval = pairs[0]
        return rtnval

    def ensure(self, *, desired: CloudKeyPair, run_id: str,
               default_tags: List[Dict[str, str]],
               aspects: Any) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for a KeyPair.

            :param desired: Desired CloudKeyPair.
            :param run_id: Run identifier.
            :param default_tags: Venue default tags.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the imported key pair.
        """
        client = self._ec2()
        existing = self.find(run_id=run_id, name=desired.name)

        if existing is None:
            neutral_tags = base_resource_tags(
                run_id=run_id, resource_name=desired.name,
                resource_kind=self.KIND, defaults=default_tags,
            )
            tag_specs = tag_specifications(
                resource_type="key-pair", neutral_tags=neutral_tags
            )
            aws_name = self._aws_keyname(run_id=run_id, name=desired.name)
            created = client.import_key_pair(
                KeyName=aws_name,
                PublicKeyMaterial=desired.public_key_material.encode("utf-8"),
                TagSpecifications=tag_specs,
            )
            existing = {
                "KeyPairId": created.get("KeyPairId", ""),
                "KeyName": aws_name,
                "KeyFingerprint": created.get("KeyFingerprint", ""),
                "Tags": [],
            }

        attributes: Dict[str, Any] = {}
        attributes["key_pair_id"] = existing.get("KeyPairId", "")
        attributes["aws_key_name"] = existing.get("KeyName", "")
        attributes["fingerprint"] = existing.get("KeyFingerprint", "")

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name,
            venue_id=existing.get("KeyPairId", ""),
            attributes=attributes,
            tags=from_aws(aws_tags=existing.get("Tags", [])),
        )
        return rtnval

    def destroy(self, *, run_id: str, aspects: Any) -> List[str]:
        """
            Destroy every owned key pair for the run.

            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of destroyed KeyPair ids.
        """
        client = self._ec2()
        deleted: List[str] = []
        owner_only = [
            {"Name": "tag:automojo:owned-by",
             "Values": ["automojo-provisioning"]},
            {"Name": "tag:automojo:owner", "Values": [run_id]},
        ]
        try:
            response = client.describe_key_pairs(Filters=owner_only)
        except Exception:
            rtnval = deleted
            return rtnval

        for pair in response.get("KeyPairs", []):
            kp_id = pair.get("KeyPairId", "")
            kp_name = pair.get("KeyName", "")
            deleted_one = False
            if len(kp_name) > 0:
                try:
                    client.delete_key_pair(KeyName=kp_name)
                    deleted.append(kp_id if len(kp_id) > 0 else kp_name)
                    deleted_one = True
                except Exception:
                    deleted_one = False
            if deleted_one is False and len(kp_id) > 0:
                try:
                    client.delete_key_pair(KeyPairId=kp_id)
                    deleted.append(kp_id)
                except Exception:
                    pass

        rtnval = deleted
        return rtnval

    def list_owned(self, *, run_id: str) -> List[ProvisionedResource]:
        """
            Return all owned key pairs for the run.

            :param run_id: Run identifier.

            :returns: List of ProvisionedResource entries.
        """
        client = self._ec2()
        owner_only = [
            {"Name": "tag:automojo:owned-by",
             "Values": ["automojo-provisioning"]},
            {"Name": "tag:automojo:owner", "Values": [run_id]},
        ]
        out: List[ProvisionedResource] = []
        try:
            response = client.describe_key_pairs(Filters=owner_only)
        except Exception:
            rtnval = out
            return rtnval
        for pair in response.get("KeyPairs", []):
            tag_flat = tag_dict_from_aws(aws_tags=pair.get("Tags", []))
            name = tag_flat.get(RESOURCE_NAME_TAG_KEY, "")
            if len(name) == 0:
                continue
            attributes: Dict[str, Any] = {}
            attributes["key_pair_id"] = pair.get("KeyPairId", "")
            attributes["aws_key_name"] = pair.get("KeyName", "")
            entry = ProvisionedResource(
                kind=self.KIND, name=name,
                venue_id=pair.get("KeyPairId", ""),
                attributes=attributes,
                tags=from_aws(aws_tags=pair.get("Tags", [])),
            )
            out.append(entry)
        rtnval = out
        return rtnval
