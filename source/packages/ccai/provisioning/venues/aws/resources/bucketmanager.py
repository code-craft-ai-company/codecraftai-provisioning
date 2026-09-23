"""
    .. module:: bucketmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: AWS S3 Bucket manager for the AWS venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from ccai.provisioning.model.cloud.cloudobjectbucket import (
    CloudObjectBucket
)
from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.venues.aws.awsboto3sessionfactory import (
    AwsBoto3SessionFactory
)
from ccai.provisioning.venues.aws.awsidempotency import tag_dict_from_aws
from ccai.provisioning.venues.aws.awstagging import (
    base_resource_tags, to_aws, from_aws, RESOURCE_NAME_TAG_KEY,
    OWNER_TAG_KEY, OWNER_TAG_VALUE, RUN_ID_TAG_KEY
)


def _aws_bucket_name(*, run_id: str, name: str) -> str:
    """
        Build the run-scoped S3 bucket name (DNS-safe).

        :param run_id: Run identifier (lowercased).
        :param name: Neutral bucket name.

        :returns: AWS bucket name.
    """
    safe_run = run_id.lower().replace("_", "-")
    safe_name = name.lower().replace("_", "-")
    rtnval = "codecraftai-{}-{}".format(safe_run, safe_name)
    return rtnval


class BucketManager:
    """
        Manager for AWS S3 Buckets.
    """

    KIND: str = "bucket"

    def __init__(self, *, session_factory: AwsBoto3SessionFactory) -> None:
        """
            Construct a BucketManager.

            :param session_factory: AwsBoto3SessionFactory.
        """
        self._session_factory: AwsBoto3SessionFactory = session_factory
        return

    def _s3(self) -> Any:
        rtnval = self._session_factory.client(service_name="s3")
        return rtnval

    def _bucket_tags(self, *, bucket_name: str) -> Optional[List[Dict[str, str]]]:
        """
            Read the tag set of an S3 bucket if any.

            :param bucket_name: AWS bucket name.

            :returns: AWS Tags list or None.
        """
        client = self._s3()
        try:
            response = client.get_bucket_tagging(Bucket=bucket_name)
        except Exception:
            rtnval: Optional[List[Dict[str, str]]] = None
            return rtnval
        rtnval = response.get("TagSet", [])
        return rtnval

    def find(self, *, run_id: str, name: str) -> Optional[Dict[str, Any]]:
        """
            Find an existing owned bucket by tag check.

            :param run_id: Run identifier.
            :param name: Neutral bucket name.

            :returns: ``{"Name": aws_name, "Tags": [...]}`` or None.
        """
        client = self._s3()
        aws_name = _aws_bucket_name(run_id=run_id, name=name)
        try:
            client.head_bucket(Bucket=aws_name)
        except Exception:
            rtnval: Optional[Dict[str, Any]] = None
            return rtnval

        tags = self._bucket_tags(bucket_name=aws_name)
        if tags is None:
            rtnval = {"Name": aws_name, "Tags": []}
            return rtnval
        rtnval = {"Name": aws_name, "Tags": tags}
        return rtnval

    def ensure(self, *, desired: CloudObjectBucket, run_id: str,
               default_tags: List[Dict[str, str]],
               aspects: Any) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for an S3 bucket.

            :param desired: Desired CloudObjectBucket.
            :param run_id: Run identifier.
            :param default_tags: Venue default tags.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the bucket.
        """
        client = self._s3()
        aws_name = _aws_bucket_name(run_id=run_id, name=desired.name)
        existing = self.find(run_id=run_id, name=desired.name)

        if existing is None:
            create_kwargs: Dict[str, Any] = {"Bucket": aws_name}
            if desired.region != "us-east-1":
                create_kwargs["CreateBucketConfiguration"] = {
                    "LocationConstraint": desired.region
                }
            client.create_bucket(**create_kwargs)

            neutral_tags = base_resource_tags(
                run_id=run_id, resource_name=desired.name,
                resource_kind=self.KIND, extra=dict(desired.tags),
                defaults=default_tags,
            )
            client.put_bucket_tagging(
                Bucket=aws_name,
                Tagging={"TagSet": to_aws(neutral_tags=neutral_tags)},
            )
            existing = {"Name": aws_name, "Tags": self._bucket_tags(
                bucket_name=aws_name
            ) or []}

        attributes: Dict[str, Any] = {}
        attributes["bucket_name"] = aws_name
        attributes["region"] = desired.region
        attributes["versioning"] = desired.versioning

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name, venue_id=aws_name,
            attributes=attributes,
            tags=from_aws(aws_tags=existing.get("Tags", [])),
        )
        return rtnval

    def destroy(self, *, run_id: str, aspects: Any) -> List[str]:
        """
            Destroy every owned S3 bucket for the run.

            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of destroyed bucket names.
        """
        client = self._s3()
        deleted: List[str] = []
        try:
            response = client.list_buckets()
        except Exception:
            rtnval = deleted
            return rtnval
        for entry in response.get("Buckets", []):
            bname = entry.get("Name", "")
            tags = self._bucket_tags(bucket_name=bname)
            flat = tag_dict_from_aws(aws_tags=tags) if tags is not None else {}
            if flat.get(OWNER_TAG_KEY, None) != OWNER_TAG_VALUE:
                continue
            if flat.get(RUN_ID_TAG_KEY, None) != run_id:
                continue
            try:
                client.delete_bucket(Bucket=bname)
                deleted.append(bname)
            except Exception:
                # Best-effort teardown sweep; a resource that fails to delete is left out
                # of the returned list and the sweep continues with the remaining resources.
                pass
        rtnval = deleted
        return rtnval

    def list_owned(self, *, run_id: str) -> List[ProvisionedResource]:
        """
            Return every owned S3 bucket for the run.

            :param run_id: Run identifier.

            :returns: List of ProvisionedResource entries.
        """
        client = self._s3()
        out: List[ProvisionedResource] = []
        try:
            response = client.list_buckets()
        except Exception:
            rtnval = out
            return rtnval
        for entry in response.get("Buckets", []):
            bname = entry.get("Name", "")
            tags = self._bucket_tags(bucket_name=bname)
            flat = tag_dict_from_aws(aws_tags=tags) if tags is not None else {}
            if flat.get(OWNER_TAG_KEY, None) != OWNER_TAG_VALUE:
                continue
            if flat.get(RUN_ID_TAG_KEY, None) != run_id:
                continue
            neutral_name = flat.get(RESOURCE_NAME_TAG_KEY, "")
            if len(neutral_name) == 0:
                continue
            attributes: Dict[str, Any] = {}
            attributes["bucket_name"] = bname
            resource = ProvisionedResource(
                kind=self.KIND, name=neutral_name, venue_id=bname,
                attributes=attributes,
                tags=from_aws(aws_tags=tags),
            )
            out.append(resource)
        rtnval = out
        return rtnval
