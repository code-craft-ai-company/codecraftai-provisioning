"""
    .. module:: spacesmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: DigitalOcean Spaces (object storage) bucket manager.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List

from ccai.provisioning.model.cloud.cloudobjectbucket import (
    CloudObjectBucket
)
from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.venues.digitalocean.doclient import (
    DigitalOceanClient
)
from ccai.provisioning.venues.digitalocean.dotagtranslator import (
    base_resource_tags
)
from ccai.restclient.digitalocean.digitaloceanapierror import (
    SpacesRequestError
)


class SpacesManager:
    """
        Manager for DigitalOcean Spaces buckets.

        Spaces is an S3-compatible object store; the DigitalOcean REST API
        cannot manage its buckets, so the venue talks to it through an
        S3-compatible client obtained from
        ``DigitalOceanClient.spaces(region=...)`` and uses the S3
        ``head_bucket`` / ``create_bucket`` / ``delete_bucket`` operations.
        Buckets are matched by the ``codecraftai-<run-id>-<name>`` naming
        convention because Spaces does not carry first-class tags.
    """

    KIND: str = "bucket"

    def __init__(self, *, client: DigitalOceanClient) -> None:
        """
            Construct a SpacesManager.

            :param client: DigitalOceanClient.
        """
        self._client: DigitalOceanClient = client
        return

    @staticmethod
    def _bucket_name(*, run_id: str, name: str) -> str:
        """
            Compute the run-scoped Spaces bucket name.

            :param run_id: Run identifier.
            :param name: Neutral bucket name.

            :returns: The Spaces bucket name.
        """
        rtnval = "codecraftai-{}-{}".format(run_id, name)
        return rtnval

    def _bucket_exists(self, *, bucket: str, region: str) -> bool:
        """
            Return whether a Spaces bucket exists via an S3 ``head_bucket``.

            The S3 API signals a missing bucket with a 404/NoSuchBucket code;
            that one case is recovered to ``False``.  Any other error (auth,
            throttle) is allowed to bubble rather than be masked as "does not
            exist" — masking one would make every apply try to create a bucket
            it cannot see.

            :param bucket: The Spaces bucket name.
            :param region: Spaces region slug.

            :returns: True when the bucket exists.
        """
        s3 = self._client.spaces(region=region)
        try:
            s3.head_bucket(Bucket=bucket)
        except SpacesRequestError as xcpt:
            if xcpt.code in ("404", "NoSuchBucket", "NotFound"):
                rtnval = False
                return rtnval
            raise

        rtnval = True
        return rtnval

    def find(self, *, run_id: str, name: str, region: str) -> bool:
        """
            Determine whether the Spaces bucket already exists.

            :param run_id: Run identifier.
            :param name: Neutral bucket name.
            :param region: Spaces region slug.

            :returns: True when the bucket exists.
        """
        bucket = self._bucket_name(run_id=run_id, name=name)
        rtnval = self._bucket_exists(bucket=bucket, region=region)
        return rtnval

    def ensure(self, *, desired: CloudObjectBucket, run_id: str,
               region: str, default_tags: List[Dict[str, str]],
               aspects: Any = None) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for a Spaces bucket.

            :param desired: Desired CloudObjectBucket.
            :param run_id: Run identifier.
            :param region: Spaces region slug.
            :param default_tags: Venue default tags.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the bucket.
        """
        bucket = self._bucket_name(run_id=run_id, name=desired.name)
        effective_region = desired.region if desired.region is not None else region
        exists = self._bucket_exists(bucket=bucket, region=effective_region)
        if exists is not True:
            s3 = self._client.spaces(region=effective_region)
            s3.create_bucket(Bucket=bucket)

        neutral_tags = base_resource_tags(
            run_id=run_id, resource_name=desired.name,
            resource_kind=self.KIND, extra=dict(desired.tags),
            defaults=default_tags,
        )
        attributes: Dict[str, Any] = {}
        attributes["bucket"] = bucket
        attributes["region"] = effective_region

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name, venue_id=bucket,
            attributes=attributes, tags=neutral_tags,
        )
        return rtnval

    def destroy(self, *, run_id: str, names: List[str], region: str,
                aspects: Any) -> List[str]:
        """
            Destroy Spaces buckets created for the run.

            :param run_id: Run identifier.
            :param names: Neutral bucket names from the run's spec.
            :param region: Spaces region slug.
            :param aspects: Aspects.

            :returns: List of destroyed bucket names.
        """
        deleted: List[str] = []
        for name in names:
            bucket = self._bucket_name(run_id=run_id, name=name)
            try:
                s3 = self._client.spaces(region=region)
                s3.delete_bucket(Bucket=bucket)
                deleted.append(bucket)
            except Exception:
                pass
        rtnval = deleted
        return rtnval

    def list_owned(self, *, run_id: str, names: List[str], region: str
                   ) -> List[ProvisionedResource]:
        """
            Return owned Spaces buckets for the run as ProvisionedResources.

            :param run_id: Run identifier.
            :param names: Neutral bucket names from the run's spec.
            :param region: Spaces region slug.

            :returns: List of ProvisionedResource entries.
        """
        out: List[ProvisionedResource] = []
        for name in names:
            bucket = self._bucket_name(run_id=run_id, name=name)
            exists = self._bucket_exists(bucket=bucket, region=region)
            if exists is not True:
                continue
            attributes: Dict[str, Any] = {}
            attributes["bucket"] = bucket
            attributes["region"] = region
            entry = ProvisionedResource(
                kind=self.KIND, name=name, venue_id=bucket,
                attributes=attributes, tags={},
            )
            out.append(entry)
        rtnval = out
        return rtnval
