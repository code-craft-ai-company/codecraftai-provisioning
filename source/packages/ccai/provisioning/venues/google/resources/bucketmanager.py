"""
    .. module:: bucketmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: GCS bucket manager for the Google venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from ccai.restclient.google import storageclient as storage

from ccai.provisioning.model.cloud.cloudobjectbucket import (
    CloudObjectBucket
)
from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.venues.google.gcpoperations import labels_of
from ccai.provisioning.venues.google.gcpsessionfactory import (
    GcpSessionFactory, SERVICE_STORAGE
)
from ccai.provisioning.venues.google.gcpidempotency import (
    belongs_to_run
)
from ccai.provisioning.venues.google.gcptagging import (
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
    rtnval = "codecraftai-{}-{}".format(safe_run, safe_name)
    return rtnval


def _owned_prefix(*, run_id: str) -> str:
    """
        Build the run-scoped bucket-name prefix for owned-bucket listing.

        :param run_id: Run identifier.

        :returns: The bucket-name prefix for this run.
    """
    safe_run = run_id.lower().replace("_", "-")
    rtnval = "codecraftai-{}-".format(safe_run)
    return rtnval


class BucketManager:
    """
        Manager for GCS buckets.

        Bucket names are globally unique, so the run-id is folded into the
        bucket name.  Idempotent ``ensure`` is done via a read-before-create
        ``lookup_bucket``.  GCS buckets carry native labels, so ownership uses
        the standard label pair.
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

    def find(self, *, run_id: str, name: str) -> Optional[Any]:
        """
            Find an existing owned GCS bucket by run+name.

            :param run_id: Run identifier.
            :param name: Neutral bucket name.

            :returns: The bucket resource, or None.
        """
        client = self._client()
        gcs_name = gcs_bucket_name(run_id=run_id, name=name)
        existing = client.lookup_bucket(gcs_name)
        if existing is None:
            rtnval: Optional[Any] = None
            return rtnval

        if not belongs_to_run(labels=labels_of(resource=existing),
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
                resource_kind=self.KIND, extra=dict(desired.tags),
                defaults=default_tags,
            )
            new_bucket = storage.Bucket(client=client, name=gcs_name)
            new_bucket.labels = labels
            new_bucket.versioning_enabled = bool(desired.versioning)
            existing = client.create_bucket(new_bucket,
                                            location=desired.region)

        location = (
            existing.location if existing.location is not None
            else desired.region
        )

        attributes: Dict[str, Any] = {}
        attributes["bucket_name"] = gcs_name
        attributes["location"] = location

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name, venue_id=gcs_name,
            attributes=attributes,
            tags=from_labels(labels=labels_of(resource=existing)),
        )
        return rtnval

    def destroy(self, *, run_id: str, aspects: Any) -> List[str]:
        """
            Destroy every owned GCS bucket for the run.

            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of destroyed bucket names.
        """
        deleted: List[str] = []
        for entry in self.list_raw(run_id=run_id):
            gcs_name = entry.name
            if len(gcs_name) == 0:
                continue
            try:
                entry.delete(force=True)
                deleted.append(gcs_name)
            except Exception:
                # Best-effort teardown sweep; a resource that fails to delete is left out
                # of the returned list and the sweep continues with the remaining resources.
                pass
        rtnval = deleted
        return rtnval

    def list_raw(self, *, run_id: str) -> List[Any]:
        """
            Return raw owned GCS bucket resources for the run.

            :param run_id: Run identifier.

            :returns: List of bucket resources.
        """
        client = self._client()
        prefix = _owned_prefix(run_id=run_id)
        out: List[Any] = []
        for entry in client.list_buckets(prefix=prefix):
            if belongs_to_run(labels=labels_of(resource=entry),
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
            labels = labels_of(resource=entry)
            name = labels.get(RESOURCE_NAME_LABEL_KEY, "")
            if len(name) == 0:
                continue
            location = entry.location if entry.location is not None else ""
            attributes: Dict[str, Any] = {}
            attributes["bucket_name"] = entry.name
            attributes["location"] = location
            resource = ProvisionedResource(
                kind=self.KIND, name=name,
                venue_id=entry.name,
                attributes=attributes,
                tags=from_labels(labels=labels),
            )
            out.append(resource)
        rtnval = out
        return rtnval
