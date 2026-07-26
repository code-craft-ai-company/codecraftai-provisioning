"""
    .. module:: objectstoragemanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: OCI Object Storage bucket manager for the Oracle Cloud venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []

from ccai.restclient.oracle import ocimodels

from ccai.restclient.oracle.ocipagination import (
    list_call_get_all_results
)


from typing import Any, Dict, List, Optional

from ccai.provisioning.model.cloud.cloudobjectbucket import (
    CloudObjectBucket
)
from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.venues.oracle.ocisessionfactory import (
    OciSessionFactory
)
from ccai.provisioning.venues.oracle.ociidempotency import (
    belongs_to_run, resource_name_of
)
from ccai.provisioning.venues.oracle.ocitagging import (
    base_resource_tags, from_freeform, to_freeform
)


def oci_bucket_name(*, run_id: str, name: str) -> str:
    """
        Build the run-scoped OCI Object Storage bucket name.

        :param run_id: Run identifier.
        :param name: Neutral bucket name.

        :returns: An OCI bucket name string.
    """
    safe_run = run_id.replace("_", "-")
    safe_name = name.replace("_", "-")
    rtnval = "codecraftai-{}-{}".format(safe_run, safe_name)
    return rtnval




class ObjectStorageManager:
    """
        Manager for OCI Object Storage buckets.

        Buckets live inside a namespace (per-tenancy).  Idempotent ``ensure``
        is done by ``get_bucket`` followed by an owner-tag check.
    """

    KIND: str = "bucket"

    def __init__(self, *, session_factory: OciSessionFactory) -> None:
        """
            Construct an ObjectStorageManager.

            :param session_factory: OciSessionFactory.
        """
        self._session_factory: OciSessionFactory = session_factory
        self._namespace: Optional[str] = None
        return

    def _os(self) -> Any:
        """
            Return the OCI ObjectStorageClient.

            :returns: An ``oci`` ObjectStorageClient.
        """
        rtnval = self._session_factory.client(service_name="object_storage")
        return rtnval

    def namespace(self) -> str:
        """
            Return the Object Storage namespace, caching it on first call.

            :returns: The tenancy namespace string.
        """
        if self._namespace is not None:
            rtnval = self._namespace
            return rtnval
        client = self._os()
        response = client.get_namespace()
        self._namespace = response.data
        rtnval = self._namespace
        return rtnval

    def find(self, *, run_id: str, name: str) -> Optional[Any]:
        """
            Find an existing owned bucket by name + owner-tag check.

            :param run_id: Run identifier.
            :param name: Neutral bucket name.

            :returns: An OCI Bucket model object or None.
        """
        client = self._os()
        bucket_name = oci_bucket_name(run_id=run_id, name=name)
        try:
            response = client.get_bucket(
                namespace_name=self.namespace(), bucket_name=bucket_name
            )
        except Exception:
            rtnval: Optional[Any] = None
            return rtnval
        bucket = response.data
        if not belongs_to_run(entity=bucket, run_id=run_id):
            rtnval = None
            return rtnval
        rtnval = bucket
        return rtnval

    def ensure(self, *, desired: CloudObjectBucket, run_id: str,
               default_tags: List[Dict[str, str]],
               aspects: Any) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for an Object Storage bucket.

            :param desired: Desired CloudObjectBucket.
            :param run_id: Run identifier.
            :param default_tags: Venue default tags.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the bucket.
        """

        client = self._os()
        compartment_id = self._session_factory.region_config.compartment_id
        bucket_name = oci_bucket_name(run_id=run_id, name=desired.name)
        existing = self.find(run_id=run_id, name=desired.name)

        if existing is None:
            neutral_tags = base_resource_tags(
                run_id=run_id, resource_name=desired.name,
                resource_kind=self.KIND, extra=dict(desired.tags),
                defaults=default_tags,
            )
            details = ocimodels.CreateBucketDetails(
                name=bucket_name,
                compartment_id=compartment_id,
                freeform_tags=to_freeform(neutral_tags=neutral_tags),
            )
            created = client.create_bucket(
                namespace_name=self.namespace(),
                create_bucket_details=details,
            )
            existing = created.data

        attributes: Dict[str, Any] = {}
        attributes["bucket_name"] = bucket_name
        attributes["namespace"] = self.namespace()
        attributes["region"] = desired.region
        attributes["versioning"] = desired.versioning

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name, venue_id=bucket_name,
            attributes=attributes,
            tags=from_freeform(
                freeform_tags=getattr(existing, "freeform_tags", None)
            ),
        )
        return rtnval

    def destroy(self, *, run_id: str, aspects: Any) -> List[str]:
        """
            Destroy every owned bucket for the run.

            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of destroyed bucket names.
        """
        client = self._os()
        compartment_id = self._session_factory.region_config.compartment_id
        deleted: List[str] = []
        try:
            response = list_call_get_all_results(
                client.list_buckets,
                namespace_name=self.namespace(),
                compartment_id=compartment_id,
            )
        except Exception:
            rtnval = deleted
            return rtnval
        for summary in response.data:
            bucket_name = getattr(summary, "name", "")
            try:
                detail = client.get_bucket(
                    namespace_name=self.namespace(),
                    bucket_name=bucket_name,
                ).data
            except Exception:
                continue
            if not belongs_to_run(entity=detail, run_id=run_id):
                continue
            try:
                client.delete_bucket(
                    namespace_name=self.namespace(),
                    bucket_name=bucket_name,
                )
                deleted.append(bucket_name)
            except Exception:
                pass
        rtnval = deleted
        return rtnval

    def list_owned(self, *, run_id: str) -> List[ProvisionedResource]:
        """
            Return every owned bucket for the run.

            :param run_id: Run identifier.

            :returns: List of ProvisionedResource entries.
        """
        client = self._os()
        compartment_id = self._session_factory.region_config.compartment_id
        out: List[ProvisionedResource] = []
        try:
            response = list_call_get_all_results(
                client.list_buckets,
                namespace_name=self.namespace(),
                compartment_id=compartment_id,
            )
        except Exception:
            rtnval = out
            return rtnval
        for summary in response.data:
            bucket_name = getattr(summary, "name", "")
            try:
                detail = client.get_bucket(
                    namespace_name=self.namespace(),
                    bucket_name=bucket_name,
                ).data
            except Exception:
                continue
            if not belongs_to_run(entity=detail, run_id=run_id):
                continue
            name = resource_name_of(entity=detail)
            if name is None:
                continue
            attributes: Dict[str, Any] = {}
            attributes["bucket_name"] = bucket_name
            attributes["namespace"] = self.namespace()
            entry = ProvisionedResource(
                kind=self.KIND, name=name, venue_id=bucket_name,
                attributes=attributes,
                tags=from_freeform(
                    freeform_tags=getattr(detail, "freeform_tags", None)
                ),
            )
            out.append(entry)
        rtnval = out
        return rtnval
