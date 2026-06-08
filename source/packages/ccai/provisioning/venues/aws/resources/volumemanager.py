"""
    .. module:: volumemanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: AWS EBS Volume manager for the AWS venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from ccai.provisioning.model.cloud.cloudstoragevolume import (
    CloudStorageVolume
)
from ccai.provisioning.model.cloud.storageclass import StorageClass
from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.venues.aws.awsboto3sessionfactory import (
    AwsBoto3SessionFactory
)
from ccai.provisioning.venues.aws.awsidempotency import (
    owner_filters, tag_dict_from_aws
)
from ccai.provisioning.venues.aws.awstagging import (
    base_resource_tags, tag_specifications, from_aws, RESOURCE_NAME_TAG_KEY
)


# Neutral StorageClass → AWS VolumeType.
_STORAGE_CLASS_MAP: Dict[StorageClass, str] = {
    StorageClass.STANDARD: "gp3",
    StorageClass.BALANCED: "gp3",
    StorageClass.PERFORMANCE: "io2",
    StorageClass.ARCHIVE: "st1",
}


def map_storage_class(*, storage_class: StorageClass) -> str:
    """
        Map a neutral StorageClass to an AWS VolumeType.

        :param storage_class: Neutral StorageClass member.

        :returns: AWS VolumeType string.
    """
    rtnval = _STORAGE_CLASS_MAP.get(storage_class, "gp3")
    return rtnval


class VolumeManager:
    """
        Manager for AWS EBS Volumes.
    """

    KIND: str = "volume"

    def __init__(self, *, session_factory: AwsBoto3SessionFactory) -> None:
        """
            Construct a VolumeManager.

            :param session_factory: AwsBoto3SessionFactory.
        """
        self._session_factory: AwsBoto3SessionFactory = session_factory
        return

    def _ec2(self) -> Any:
        rtnval = self._session_factory.client(service_name="ec2")
        return rtnval

    def find(self, *, run_id: str, name: str) -> Optional[Dict[str, Any]]:
        """
            Find an existing owned volume by run+name tags.

            :param run_id: Run identifier.
            :param name: Neutral volume name.

            :returns: A volume dict or None.
        """
        client = self._ec2()
        filters = owner_filters(run_id=run_id, resource_name=name)
        response = client.describe_volumes(Filters=filters)
        volumes = response.get("Volumes", [])
        if len(volumes) == 0:
            rtnval: Optional[Dict[str, Any]] = None
            return rtnval
        rtnval = volumes[0]
        return rtnval

    def ensure(self, *, desired: CloudStorageVolume, run_id: str,
               availability_zone: str,
               default_tags: List[Dict[str, str]],
               attach_instance_id: Optional[str],
               aspects: Any) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for an EBS volume.

            :param desired: Desired CloudStorageVolume.
            :param run_id: Run identifier.
            :param availability_zone: AZ to create the volume in.
            :param default_tags: Venue default tags.
            :param attach_instance_id: AWS instance id to attach to or None.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the volume.
        """
        client = self._ec2()
        existing = self.find(run_id=run_id, name=desired.name)

        if existing is None:
            neutral_tags = base_resource_tags(
                run_id=run_id, resource_name=desired.name,
                resource_kind=self.KIND, extra=dict(desired.tags),
                defaults=default_tags,
            )
            tag_specs = tag_specifications(
                resource_type="volume", neutral_tags=neutral_tags
            )
            created = client.create_volume(
                AvailabilityZone=availability_zone,
                Size=desired.size_gb,
                VolumeType=map_storage_class(storage_class=desired.storage_class),
                TagSpecifications=tag_specs,
            )
            existing = created

        vol_id = existing.get("VolumeId", "")

        if attach_instance_id is not None and len(attach_instance_id) > 0:
            device = desired.mount if desired.mount is not None else "/dev/sdf"
            try:
                client.attach_volume(
                    VolumeId=vol_id,
                    InstanceId=attach_instance_id,
                    Device=device,
                )
            except Exception:
                pass

        attributes: Dict[str, Any] = {}
        attributes["volume_id"] = vol_id
        attributes["size_gb"] = existing.get("Size", desired.size_gb)
        attributes["volume_type"] = existing.get(
            "VolumeType", map_storage_class(storage_class=desired.storage_class)
        )
        attributes["availability_zone"] = existing.get(
            "AvailabilityZone", availability_zone
        )

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name, venue_id=vol_id,
            attributes=attributes,
            tags=from_aws(aws_tags=existing.get("Tags", [])),
        )
        return rtnval

    def destroy(self, *, run_id: str, aspects: Any) -> List[str]:
        """
            Destroy every owned EBS volume for the run.

            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of destroyed volume ids.
        """
        client = self._ec2()
        owner_only = [
            {"Name": "tag:ccai:owned-by",
             "Values": ["codecraftai-provisioning"]},
            {"Name": "tag:ccai:owner", "Values": [run_id]},
        ]
        response = client.describe_volumes(Filters=owner_only)
        deleted: List[str] = []
        for volume in response.get("Volumes", []):
            vol_id = volume.get("VolumeId", "")
            for attachment in volume.get("Attachments", []):
                try:
                    client.detach_volume(
                        VolumeId=vol_id,
                        InstanceId=attachment.get("InstanceId", ""),
                        Force=True,
                    )
                except Exception:
                    pass
            try:
                client.delete_volume(VolumeId=vol_id)
                deleted.append(vol_id)
            except Exception:
                pass
        rtnval = deleted
        return rtnval

    def list_owned(self, *, run_id: str) -> List[ProvisionedResource]:
        """
            Return every owned EBS volume for the run.

            :param run_id: Run identifier.

            :returns: List of ProvisionedResource entries.
        """
        client = self._ec2()
        owner_only = [
            {"Name": "tag:ccai:owned-by",
             "Values": ["codecraftai-provisioning"]},
            {"Name": "tag:ccai:owner", "Values": [run_id]},
        ]
        response = client.describe_volumes(Filters=owner_only)
        out: List[ProvisionedResource] = []
        for volume in response.get("Volumes", []):
            tag_flat = tag_dict_from_aws(aws_tags=volume.get("Tags", []))
            name = tag_flat.get(RESOURCE_NAME_TAG_KEY, "")
            if len(name) == 0:
                continue
            attributes: Dict[str, Any] = {}
            attributes["volume_id"] = volume.get("VolumeId", "")
            attributes["size_gb"] = volume.get("Size", 0)
            attributes["volume_type"] = volume.get("VolumeType", "")
            entry = ProvisionedResource(
                kind=self.KIND, name=name,
                venue_id=volume.get("VolumeId", ""),
                attributes=attributes,
                tags=from_aws(aws_tags=volume.get("Tags", [])),
            )
            out.append(entry)
        rtnval = out
        return rtnval
