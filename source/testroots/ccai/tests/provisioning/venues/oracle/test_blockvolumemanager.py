"""
    .. module:: test_blockvolumemanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Pins which attach errors the OCI BlockVolumeManager tolerates:
               only the 409 for a volume that a listed attachment shows
               attached, or attaching, to the requested instance.  Every
               other error reaches the caller.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

from ccai import testbase

from ccai.errors.exceptions import SkipError
from ccai.restclient.oracle.ociclients import ComputeClient
from ccai.restclient.oracle.ocierror import ServiceError
from ccai.restclient.oracle.ocimodels import Response, wrap

from ccai.provisioning.model.cloud.cloudstoragevolume import (
    CloudStorageVolume
)
from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.venues.oracle.ocisessionfactory import (
    OciSessionFactory
)
from ccai.provisioning.venues.oracle.resources.blockvolumemanager import (
    BlockVolumeManager
)

from ccai.tests.provisioning.venues.oracle._ocifakes import (
    FakeBlockstorageClient, FakeComputeClient
)


_RUN_ID = "run01"

_INSTANCE_A = "ocid1.instance.oc1..aaaa"

_INSTANCE_B = "ocid1.instance.oc1..bbbb"


class _RefusingComputeClient(FakeComputeClient):
    """
        A FakeComputeClient whose attach always fails with a given error,
        while listing whatever attachments the test seeds.
    """

    def __init__(self, *, failure: ServiceError) -> None:
        """
            Construct.

            :param failure: The error every attach raises.
        """
        super().__init__()
        self._failure: ServiceError = failure
        return

    def attach_volume(self, *, attach_volume_details: Any) -> Any:
        """
            Refuse the attach.
        """
        raise self._failure


def _service_error(*, status: int, code: str) -> ServiceError:
    """
        Build a ServiceError the way the OCI transport raises one.

        :param status: The HTTP status.
        :param code: The OCI error code.

        :returns: The ServiceError.
    """
    rtnval = ServiceError("The OCI request failed. STATUS: {} CODE: {}".format(
        status, code), status=status, code=code, message=code)
    return rtnval


def _manager(*, credential: Any, region_config: Any,
             compute: Optional[FakeComputeClient] = None
             ) -> Tuple[BlockVolumeManager, FakeComputeClient]:
    """
        Build a BlockVolumeManager over the fake OCI clients.

        :param credential: The OracleCloudApiKeyCredential.
        :param region_config: The OciRegionConfig.
        :param compute: The compute fake to serve, or None for a plain one.

        :returns: The manager and the compute fake it attaches through.
    """
    if compute is None:
        compute = FakeComputeClient()

    factory = OciSessionFactory(credential=credential,
                                region_config=region_config)
    factory.register_client(service_name="compute", client=compute)
    factory.register_client(service_name="blockstorage",
                            client=FakeBlockstorageClient())

    manager = BlockVolumeManager(session_factory=factory)
    rtnval = (manager, compute)
    return rtnval


def _ensure_volume(*, manager: BlockVolumeManager,
                   instance_id: str) -> ProvisionedResource:
    """
        Run BlockVolumeManager.ensure for the test volume.

        :param manager: The BlockVolumeManager.
        :param instance_id: The instance to attach to.

        :returns: The ProvisionedResource.
    """
    desired = CloudStorageVolume(name="vol-a", size_gb=50,
                                 attached_to="inst-a", mount="/mnt/data")
    rtnval = manager.ensure(desired=desired, run_id=_RUN_ID, default_tags={},
                            attach_instance_id=instance_id, aspects=None)
    return rtnval


def _seed_attachment(*, compute: FakeComputeClient, instance_id: str,
                     volume_id: str, lifecycle_state: str) -> None:
    """
        Record an existing attachment on the compute fake.

        :param compute: The compute fake.
        :param instance_id: The attached instance.
        :param volume_id: The attached volume.
        :param lifecycle_state: The attachment's lifecycle state.
    """
    compute.volume_attachments.append(SimpleNamespace(
        id="ocid1.volumeattachment.oc1..seeded", instance_id=instance_id,
        volume_id=volume_id, lifecycle_state=lifecycle_state))
    return


def _attachments_of(*, compute: FakeComputeClient,
                    volume_id: str) -> List[Any]:
    """
        Return the attachments the compute fake holds for a volume.

        :param compute: The compute fake.
        :param volume_id: The volume.

        :returns: The attachments.
    """
    found: List[Any] = []
    for attachment in compute.volume_attachments:
        if attachment.volume_id == volume_id:
            found.append(attachment)
    rtnval = found
    return rtnval


def test_volume_reapply_tolerates_attachment_to_same_instance(
        credential, region_config) -> None:
    """
        Re-applying a volume already attached to the requested instance
        succeeds and leaves one attachment.
    """
    manager, compute = _manager(credential=credential,
                                region_config=region_config)

    first = _ensure_volume(manager=manager, instance_id=_INSTANCE_A)
    second = _ensure_volume(manager=manager, instance_id=_INSTANCE_A)

    assert second.venue_id == first.venue_id
    assert len(_attachments_of(compute=compute,
                               volume_id=first.venue_id)) == 1
    return


def test_volume_attached_to_other_instance_propagates(credential,
                                                      region_config) -> None:
    """
        A volume attached to some other instance is not reported as attached
        to the requested one.
    """
    manager, _ = _manager(credential=credential,
                          region_config=region_config)

    _ensure_volume(manager=manager, instance_id=_INSTANCE_A)

    with testbase.raises(ServiceError) as caught:
        _ensure_volume(manager=manager, instance_id=_INSTANCE_B)

    assert caught.exception.status == 409
    return


def test_volume_attach_failure_propagates(credential, region_config) -> None:
    """
        A non-conflict failure attaching a volume reaches the caller.
    """
    refusing = _RefusingComputeClient(failure=_service_error(
        status=400, code="InvalidParameter"))
    manager, _ = _manager(credential=credential,
                          region_config=region_config,
                          compute=refusing)

    with testbase.raises(ServiceError) as caught:
        _ensure_volume(manager=manager, instance_id=_INSTANCE_A)

    assert caught.exception.code == "InvalidParameter"
    return


def test_volume_conflict_without_an_attachment_propagates(
        credential, region_config) -> None:
    """
        A 409 that no listed attachment explains (the instance is in the
        wrong state, say) reaches the caller.
    """
    refusing = _RefusingComputeClient(failure=_service_error(
        status=409, code="IncorrectState"))
    manager, _ = _manager(credential=credential,
                          region_config=region_config,
                          compute=refusing)

    with testbase.raises(ServiceError) as caught:
        _ensure_volume(manager=manager, instance_id=_INSTANCE_A)

    assert caught.exception.code == "IncorrectState"
    return


def test_volume_conflict_with_a_detaching_attachment_propagates(
        credential, region_config) -> None:
    """
        A 409 while the volume is detaching from the requested instance is
        not an attach in place, so it reaches the caller.
    """
    refusing = _RefusingComputeClient(failure=_service_error(
        status=409, code="Conflict"))
    manager, _ = _manager(credential=credential,
                          region_config=region_config,
                          compute=refusing)
    volume = manager.ensure(
        desired=CloudStorageVolume(name="vol-a", size_gb=50),
        run_id=_RUN_ID, default_tags={}, attach_instance_id=None,
        aspects=None)
    _seed_attachment(compute=refusing, instance_id=_INSTANCE_A,
                     volume_id=volume.venue_id, lifecycle_state="DETACHING")

    with testbase.raises(ServiceError) as caught:
        _ensure_volume(manager=manager, instance_id=_INSTANCE_A)

    assert caught.exception.code == "Conflict"
    return


def test_volume_conflict_with_an_attaching_attachment_is_tolerated(
        credential, region_config) -> None:
    """
        A 409 while the volume is still attaching to the requested instance
        is an attach underway, so ensure succeeds.
    """
    refusing = _RefusingComputeClient(failure=_service_error(
        status=409, code="Conflict"))
    manager, _ = _manager(credential=credential,
                          region_config=region_config,
                          compute=refusing)
    volume = manager.ensure(
        desired=CloudStorageVolume(name="vol-a", size_gb=50),
        run_id=_RUN_ID, default_tags={}, attach_instance_id=None,
        aspects=None)
    _seed_attachment(compute=refusing, instance_id=_INSTANCE_A,
                     volume_id=volume.venue_id, lifecycle_state="ATTACHING")

    resource = _ensure_volume(manager=manager, instance_id=_INSTANCE_A)

    assert resource.venue_id == volume.venue_id
    return


class _AttachConflictTransport:
    """
        Stands in for the OciTransport below a REAL ComputeClient, answering
        the volume attachment calls the way OCI does for a volume that is
        already attached: 409 to the attach, and the attachment in the
        camelCase listing.
    """

    def __init__(self, *, attachments: List[Dict[str, Any]]) -> None:
        """
            Construct.

            :param attachments: The wire-shaped attachments OCI holds.
        """
        self.calls: List[Dict[str, Any]] = []
        self._attachments: List[Dict[str, Any]] = attachments
        return

    def request(self, *, method: str, url: str,
                params: Optional[Dict[str, Any]] = None,
                body: Optional[Any] = None,
                timeout_seconds: Optional[float] = None) -> Response:
        """
            Answer one Core Services call.
        """
        query: Dict[str, Any] = dict(params or {})
        self.calls.append({"method": method, "url": url, "params": query})

        if url.endswith("/volumeAttachments") is False:
            raise AssertionError("unexpected OCI call: {} {}".format(method,
                                                                    url))

        if method == "POST":
            raise ServiceError("The OCI request failed. STATUS: 409",
                               status=409, code="Conflict",
                               message="The volume is already attached.")

        listed: List[Any] = []
        for attachment in self._attachments:
            wanted_instance = query.get("instanceId", None)
            if wanted_instance is not None:
                if attachment["instanceId"] != wanted_instance:
                    continue
            wanted_volume = query.get("volumeId", None)
            if wanted_volume is not None:
                if attachment["volumeId"] != wanted_volume:
                    continue
            listed.append(wrap(attachment))

        rtnval = Response(data=listed)
        return rtnval


def test_volume_reapply_through_the_real_compute_client(
        credential, region_config) -> None:
    """
        The already-attached check works against the real ComputeClient:
        the venue's filter keywords reach OCI as ``instanceId`` /
        ``volumeId`` and the camelCase attachment reads back by attribute.
    """
    if hasattr(ComputeClient, "list_volume_attachments") is False:
        err_msg_lines = [
            "The installed codecraftai-restclient-oracle ComputeClient has "
            "no list_volume_attachments."
        ]
        err_msg_lines.append("Install a codecraftai-restclient-oracle that "
                             "provides ComputeClient.list_volume_attachments.")
        err_msg = os.linesep.join(err_msg_lines)
        raise SkipError(err_msg)

    manager, _ = _manager(credential=credential,
                          region_config=region_config)
    volume = manager.ensure(
        desired=CloudStorageVolume(name="vol-a", size_gb=50),
        run_id=_RUN_ID, default_tags={}, attach_instance_id=None,
        aspects=None)

    transport = _AttachConflictTransport(attachments=[
        {"id": "ocid1.volumeattachment.oc1..other", "instanceId": _INSTANCE_B,
         "volumeId": "ocid1.volume.oc1..other",
         "lifecycleState": "ATTACHED"},
        {"id": "ocid1.volumeattachment.oc1..here", "instanceId": _INSTANCE_A,
         "volumeId": volume.venue_id, "lifecycleState": "ATTACHED"},
    ])
    real_compute = ComputeClient(transport=transport, region="us-ashburn-1")
    manager._session_factory.register_client(service_name="compute",
                                             client=real_compute)

    resource = _ensure_volume(manager=manager, instance_id=_INSTANCE_A)

    listing_call = transport.calls[1]
    assert resource.venue_id == volume.venue_id
    assert listing_call["method"] == "GET"
    assert listing_call["params"]["instanceId"] == _INSTANCE_A
    assert listing_call["params"]["volumeId"] == volume.venue_id
    return
