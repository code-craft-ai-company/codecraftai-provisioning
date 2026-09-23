"""
    .. module:: placementgroupmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: AWS Cluster placement group manager (EFA / RAIL_OPTIMIZED).

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List

from ccai.restclient.aws.awserror import ClientError

from ccai.provisioning.venues.aws.awsboto3sessionfactory import (
    AwsBoto3SessionFactory
)
from ccai.provisioning.venues.aws.awsidempotency import owner_filters
from ccai.provisioning.venues.aws.awstagging import (
    base_resource_tags, tag_specifications
)


class PlacementGroupManager:
    """
        Manager for AWS cluster placement groups used by EFA-enabled
        instance launches.

        ``ensure`` is idempotent; the group is named from the run id +
        a logical apod-style name.
    """

    KIND: str = "placement_group"

    def __init__(self, *, session_factory: AwsBoto3SessionFactory) -> None:
        """
            Construct a PlacementGroupManager.

            :param session_factory: AwsBoto3SessionFactory.
        """
        self._session_factory: AwsBoto3SessionFactory = session_factory
        return

    def _ec2(self) -> Any:
        rtnval = self._session_factory.client(service_name="ec2")
        return rtnval

    def _aws_name(self, *, run_id: str, logical_name: str) -> str:
        """
            Build the AWS placement-group name (run-scoped).

            :param run_id: Run identifier.
            :param logical_name: Logical apod / group label.

            :returns: AWS placement-group name string.
        """
        rtnval = "codecraftai-pg-{}-{}".format(run_id, logical_name)
        return rtnval

    def ensure(self, *, run_id: str, logical_name: str,
               default_tags: List[Dict[str, str]],
               aspects: Any) -> str:
        """
            Create or reuse a cluster placement group.

            :param run_id: Run identifier.
            :param logical_name: Logical name (per-apod).
            :param default_tags: Venue default tags.
            :param aspects: Aspects.

            :returns: The AWS placement-group name.
        """
        client = self._ec2()
        aws_name = self._aws_name(run_id=run_id, logical_name=logical_name)

        filters = owner_filters(run_id=run_id, resource_name=logical_name)
        try:
            response = client.describe_placement_groups(Filters=filters)
        except Exception:
            response = {"PlacementGroups": []}
        groups = response.get("PlacementGroups", [])
        if len(groups) > 0:
            rtnval = groups[0].get("GroupName", aws_name)
            return rtnval

        neutral_tags = base_resource_tags(
            run_id=run_id, resource_name=logical_name,
            resource_kind=self.KIND, defaults=default_tags,
        )
        tag_specs = tag_specifications(
            resource_type="placement-group", neutral_tags=neutral_tags
        )
        try:
            client.create_placement_group(
                GroupName=aws_name, Strategy="cluster",
                TagSpecifications=tag_specs,
            )
        except ClientError as xcpt:
            # The owner-tag lookup above can miss a group that already holds
            # this run-scoped name, e.g. while describe lags a create that just
            # finished.  EC2 then answers InvalidPlacementGroup.Duplicate and
            # the named group exists, which is what ensure promises.  Any
            # other error is real.
            if xcpt.code != "InvalidPlacementGroup.Duplicate":
                raise

        rtnval = aws_name
        return rtnval

    def destroy(self, *, run_id: str, aspects: Any) -> List[str]:
        """
            Destroy every owned placement group for the run.

            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of deleted group names.
        """
        client = self._ec2()
        owner_only = [
            {"Name": "tag:ccai:owned-by",
             "Values": ["codecraftai-provisioning"]},
            {"Name": "tag:ccai:owner", "Values": [run_id]},
        ]
        try:
            response = client.describe_placement_groups(Filters=owner_only)
        except Exception:
            response = {"PlacementGroups": []}
        deleted: List[str] = []
        for group in response.get("PlacementGroups", []):
            gname = group.get("GroupName", "")
            try:
                client.delete_placement_group(GroupName=gname)
                deleted.append(gname)
            except Exception:
                # Best-effort teardown sweep; a resource that fails to delete is left out
                # of the returned list and the sweep continues with the remaining resources.
                pass
        rtnval = deleted
        return rtnval
