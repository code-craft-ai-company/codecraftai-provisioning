"""
    .. module:: test_blobmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Pins how the Azure BlobManager realises the blob container of
               a bucket: it is created through the real client's
               ``blob_containers`` group, reused when present, and a failed
               create reaches the caller.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import inspect
import os

from typing import Any, Dict, List, Optional

from ccai import testbase

from ccai.errors.exceptions import SkipError
from ccai.restclient.azure.azurearmerror import AzureRequestError

from ccai.provisioning.model.cloud.cloudobjectbucket import (
    CloudObjectBucket
)
from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.venues.azure.azuresessionfactory import (
    AzureSessionFactory
)
from ccai.provisioning.venues.azure.resources.blobmanager import (
    BlobManager, storage_account_name
)

from ccai.tests.provisioning.venues.azure._fakeazure import (
    FakeResource, _BlobContainersOps
)
from ccai.tests.provisioning.venues.azure.factories import (
    create_azure_session_factory, create_azure_world
)


_RUN_ID = "testrun01"

_RESOURCE_GROUP = "rg-testrun01"

_BUCKET_NAME = "bkta"


class _RecordingBlobContainersOps(_BlobContainersOps):
    """
        A ``blob_containers`` double that counts creates and can be told to
        refuse them the way ARM does.
    """

    def __init__(self, *, store: Dict[str, FakeResource],
                 accounts: Dict[str, FakeResource],
                 failure: Optional[Exception] = None) -> None:
        """
            Construct.

            :param store: Backing containers dict.
            :param accounts: Backing storage accounts dict.
            :param failure: The error every create raises, or None.
        """
        super().__init__(store=store, accounts=accounts)
        self.create_calls: int = 0
        self._failure: Optional[Exception] = failure
        return

    def create(self, *, resource_group_name: str, account_name: str,
               container_name: str,
               blob_container: Dict[str, Any]) -> FakeResource:
        """
            Count the create, then refuse it or store the container.
        """
        self.create_calls = self.create_calls + 1
        if self._failure is not None:
            raise self._failure

        rtnval = super().create(resource_group_name=resource_group_name,
                                account_name=account_name,
                                container_name=container_name,
                                blob_container=blob_container)
        return rtnval


def _install_ops(*, session_factory: AzureSessionFactory, world: Any,
                 failure: Optional[Exception] = None
                 ) -> _RecordingBlobContainersOps:
    """
        Swap the storage client's ``blob_containers`` for a recording double.

        :param session_factory: The session factory serving the fake clients.
        :param world: The FakeAzureWorld backing them.
        :param failure: The error every create raises, or None.

        :returns: The installed double.
    """
    storage = session_factory.storage_client()
    ops = _RecordingBlobContainersOps(store=world.blob_containers,
                                      accounts=world.storage_accounts,
                                      failure=failure)
    storage.blob_containers = ops
    rtnval = ops
    return rtnval


def _ensure_bucket(*, session_factory: AzureSessionFactory,
                   aspects: Any) -> ProvisionedResource:
    """
        Run BlobManager.ensure for the test bucket.

        :param session_factory: The session factory serving the fake clients.
        :param aspects: The ProvisioningAspects.

        :returns: The ProvisionedResource.
    """
    manager = BlobManager(session_factory=session_factory)
    desired = CloudObjectBucket(name=_BUCKET_NAME, region="eastus")
    rtnval = manager.ensure(desired=desired, resource_group=_RESOURCE_GROUP,
                            location="eastus", run_id=_RUN_ID,
                            default_tags={}, aspects=aspects)
    return rtnval


def _container_key() -> str:
    """
        Build the fake world's key for the test bucket's container.

        :returns: The ``<rg>/<account>/<container>`` key.
    """
    account = storage_account_name(run_id=_RUN_ID, name=_BUCKET_NAME)
    rtnval = "{}/{}/{}".format(_RESOURCE_GROUP, account, _BUCKET_NAME)
    return rtnval


@testbase.attach.parameter(create_azure_session_factory, identifier="session_factory")
@testbase.attach.parameter(create_azure_world, identifier="world")
def test_ensure_creates_the_blob_container(credential, region_config, world,
                                          session_factory, aspects) -> None:
    """
        Ensuring a bucket creates its blob container inside the new storage
        account.
    """
    _ensure_bucket(session_factory=session_factory, aspects=aspects)

    assert _container_key() in world.blob_containers
    return


@testbase.attach.parameter(create_azure_session_factory, identifier="session_factory")
@testbase.attach.parameter(create_azure_world, identifier="world")
def test_ensure_container_failure_propagates(credential, region_config,
                                             world, session_factory,
                                             aspects) -> None:
    """
        A failed container create reaches the caller rather than reporting a
        bucket that has no container.
    """
    refusal = AzureRequestError("The Azure Resource Manager request failed.",
                                status_code=403, code="AuthorizationFailed")
    _install_ops(session_factory=session_factory, world=world,
                 failure=refusal)

    with testbase.raises(AzureRequestError) as caught:
        _ensure_bucket(session_factory=session_factory, aspects=aspects)

    assert caught.exception.code == "AuthorizationFailed"
    return


@testbase.attach.parameter(create_azure_session_factory, identifier="session_factory")
@testbase.attach.parameter(create_azure_world, identifier="world")
def test_ensure_reuses_an_existing_container(credential, region_config,
                                            world, session_factory,
                                            aspects) -> None:
    """
        Re-ensuring a bucket whose container exists does not create it again.
    """
    ops = _install_ops(session_factory=session_factory, world=world)

    _ensure_bucket(session_factory=session_factory, aspects=aspects)
    _ensure_bucket(session_factory=session_factory, aspects=aspects)

    assert ops.create_calls == 1
    return


@testbase.attach.parameter(create_azure_session_factory, identifier="session_factory")
@testbase.attach.parameter(create_azure_world, identifier="world")
def test_ensure_adds_a_missing_container_to_an_existing_account(
        credential, region_config, world, session_factory, aspects) -> None:
    """
        A storage account left without its container by an earlier run gets
        the container on the next ensure.
    """
    _ensure_bucket(session_factory=session_factory, aspects=aspects)
    world.blob_containers.pop(_container_key())

    _ensure_bucket(session_factory=session_factory, aspects=aspects)

    assert _container_key() in world.blob_containers
    return


def _real_blob_containers_collection() -> Any:
    """
        Import the real client's blob containers group.

        :returns: The ``BlobContainersCollection`` class.

        :raises: SkipError when the installed codecraftai-restclient-azure
            predates blob container support.
    """
    try:
        from ccai.restclient.azure.apigroups.computecollections import (
            BlobContainersCollection
        )
    except ImportError as xcpt:
        err_msg_lines = [
            "The installed codecraftai-restclient-azure has no "
            "BlobContainersCollection to compare the fake against."
        ]
        err_msg_lines.append("Install a codecraftai-restclient-azure that "
                             "provides StorageManagementClient.blob_containers.")
        err_msg = os.linesep.join(err_msg_lines)
        raise SkipError(err_msg) from xcpt

    rtnval = BlobContainersCollection
    return rtnval


class _StubTokenProvider:
    """
        A token provider that is never asked for a token.
    """

    def token(self, **kwargs: Any) -> str:
        """
            Return a placeholder token.

            :returns: The token.
        """
        rtnval = "stub-token"
        return rtnval


def test_fake_blob_containers_mirror_the_real_client() -> None:
    """
        The fake ``blob_containers`` offers only the operations, with the
        same keyword signatures, that the real client's group has.
    """
    real_collection = _real_blob_containers_collection()

    fake_operations: List[str] = []
    for name in dir(_BlobContainersOps):
        if name.startswith("_") is False:
            fake_operations.append(name)

    mismatches: List[str] = []
    for name in fake_operations:
        real_operation = getattr(real_collection, name, None)
        if real_operation is None:
            mismatches.append("{}: missing from the real client".format(name))
            continue
        real_signature = inspect.signature(real_operation)
        fake_signature = inspect.signature(getattr(_BlobContainersOps, name))
        real_parameters = [(param.name, param.kind) for param in
                           real_signature.parameters.values()]
        fake_parameters = [(param.name, param.kind) for param in
                           fake_signature.parameters.values()]
        if real_parameters != fake_parameters:
            mismatches.append("{}: real {} fake {}".format(
                name, real_signature, fake_signature))

    assert sorted(fake_operations) == ["create", "delete", "get", "list"]
    assert mismatches == []
    return


def test_real_storage_client_exposes_blob_containers() -> None:
    """
        The real StorageManagementClient carries the ``blob_containers``
        group the BlobManager calls.
    """
    real_collection = _real_blob_containers_collection()

    from ccai.restclient.azure.azurearmclient import AzureArmClient
    from ccai.restclient.azure.managementclients import (
        StorageManagementClient
    )

    arm_client = AzureArmClient(subscription_id="sub-test-0001",
                                token_provider=_StubTokenProvider(),
                                session=object())
    storage = StorageManagementClient(arm_client=arm_client)

    assert isinstance(storage.blob_containers, real_collection) is True
    return
