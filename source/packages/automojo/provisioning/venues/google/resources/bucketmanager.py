"""
    .. module:: bucketmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: GCS bucket manager for the Google venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.provisioning.model.cloud.cloudobjectbucket import (
    CloudObjectBucket
)
from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.venues.google.gcpsessionfactory import (
    GcpSessionFactory, SERVICE_STORAGE
)
from automojo.provisioning.venues.google.gcpidempotency import (
    belongs_to_run
)
from automojo.provisioning.venues.google.gcptagging import (
    base_resource_labels, from_labels, RESOURCE_NAME_LABEL_KEY
)


def gcs_bucket_name(*, run_id: str, name: str) -> str:
    """
        Build the run-scoped, globally-unique GCS bucket name.

        :param run_id: Run identifier.
        :param name: Neutral bucket name.

        :returns: A GCS-conformant bucket name.
    """
    safe_run = run_id.lower().replace("_", "-")
    safe_name = name.lower().replace("_", "-")
    rtnval = "automojo-{}-{}".format(safe_run, safe_name)
    return rtnval


class BucketManager:
    """
        Manager for GCS buckets.

        Bucket names are globally unique, so the run-id is folded into the
        bucket name.  Idempotent ``ensure`` is done via a read-before-create
        ``get_bucket``.
    """

    KIND: str = "bucket"

    def __init__(self, *, session_factory: GcpSessionFactory) -> None:
        """
            Construct a BucketManager.

            :param session_factory: GcpSessionFactory.
        """
        self._session_factory: GcpSessionFactory = session_factory
        return

    def _client(self) -> Any:
        """
            Return the GCS storage client.

            :returns: The storage client.
        """
        rtnval = self._session_factory.client(service_name=SERVICE_STORAGE)
        return rtnval

    def find(self, *, run_id: str, name: str) -> Optional[Dict[str, Any]]:
        """
            Find an existing owned GCS bucket by run+name.

            :param run_id: Run identifier.
            :param name: Neutral bucket name.

            :returns: The bucket resource dict, or None.
        """
        client = self._client()
        gcs_name = gcs_bucket_name(run_id=run_id, name=name)
        existing = client.get_bucket(bucket_name=gcs_name)
        if existing is None:
            rtnval: Optional[Dict[str, Any]] = None
            return rtnval
        if not belongs_to_run(labels=existing.get("labels", {}),
                              run_id=run_id):
            rtnval = None
            return rtnval
        rtnval = existing
        return rtnval

    def ensure(self, *, desired: CloudObjectBucket, run_id: str,
               default_tags: List[Dict[str, str]],
               aspects: Any) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for a GCS bucket.

            :param desired: Desired CloudObjectBucket.
            :param run_id: Run identifier.
            :param default_tags: Venue default tags.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the bucket.
        """
        client = self._client()
        gcs_name = gcs_bucket_name(run_id=run_id, name=desired.name)

        existing = self.find(run_id=run_id, name=desired.name)
        if existing is None:
            labels = base_resource_labels(
                run_id=run_id, resource_name=desired.name,
                resource_kind=self.KIND, extra=list(desired.tags),
                defaults=default_tags,
            )
            body: Dict[str, Any] = {
                "name": gcs_name,
                "location": desired.region,
                "labels": labels,
                "versioning": {"enabled": bool(desired.versioning)},
            }
            client.create_bucket(bucket_resource=body)
            existing = client.get_bucket(bucket_name=gcs_name)
            if existing is None:
                existing = body

        attributes: Dict[str, Any] = {}
        attributes["bucket_name"] = gcs_name
        attributes["location"] = existing.get("location", desired.region)

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name, venue_id=gcs_name,
            attributes=attributes,
            tags=from_labels(labels=existing.get("labels", {})),
        )
        return rtnval

    def destroy(self, *, run_id: str, aspects: Any) -> List[str]:
        """
            Destroy every owned GCS bucket for the run.

            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of destroyed bucket names.
        """
        client = self._client()
        deleted: List[str] = []
        for entry in self.list_raw(run_id=run_id):
            gcs_name = entry.get("name", "")
            if len(gcs_name) == 0:
                continue
            try:
                client.delete_bucket(bucket_name=gcs_name)
                deleted.append(gcs_name)
            except Exception:
                pass
        rtnval = deleted
        return rtnval

    def list_raw(self, *, run_id: str) -> List[Dict[str, Any]]:
        """
            Return raw owned GCS bucket resource dicts for the run.

            :param run_id: Run identifier.

            :returns: List of bucket resource dicts.
        """
        client = self._client()
        out: List[Dict[str, Any]] = []
        for entry in client.list_buckets():
            if belongs_to_run(labels=entry.get("labels", {}),
                              run_id=run_id):
                out.append(entry)
        rtnval = out
        return rtnval

    def list_owned(self, *, run_id: str) -> List[ProvisionedResource]:
        """
            Return all owned GCS buckets for the run as ProvisionedResources.

            :param run_id: Run identifier.

            :returns: List of ProvisionedResource entries.
        """
        out: List[ProvisionedResource] = []
        for entry in self.list_raw(run_id=run_id):
            labels = entry.get("labels", {})
            name = labels.get(RESOURCE_NAME_LABEL_KEY, "")
            if len(name) == 0:
                continue
            attributes: Dict[str, Any] = {}
            attributes["bucket_name"] = entry.get("name", "")
            attributes["location"] = entry.get("location", "")
            resource = ProvisionedResource(
                kind=self.KIND, name=name,
                venue_id=entry.get("name", ""),
                attributes=attributes,
                tags=from_labels(labels=labels),
            )
            out.append(resource)
        rtnval = out
        return rtnval
