# Crusoe Cloud Venue

`CrusoeCloudProvisioner` realises the neutral cloud resource model on
[Crusoe Cloud](https://crusoecloud.com), a GPU-first cloud whose API shape is
the closest of the AI clouds to AWS: full VPC / subnet / security-group / VM /
disk plus first-class InfiniBand-enabled placement for multi-node training.

## Cross-references

- Neutral resource model:
  `ccai/provisioning/model/cloud/` (cloud-resource-model spec).
- Lifecycle contract: `cloud-provisioner-lifecycle` spec —
  `validate / plan / apply / destroy / inventory`.
- VPN join: `vpn-join-spec` spec; the cloud-init snippet is rendered by
  `ccai/provisioning/cloudinit/vpncloudinitrenderer.render_cloud_init`
  and folded into the instance `user_data`.
- Crusoe interop client: `codecraftai-interop-crusoe` (`CrusoeClient`,
  built on `codecraftai-restclient-base`).

## Mapping table

| Neutral model | Crusoe primitive | Notes |
| --- | --- | --- |
| `CloudNetwork` | VPC | `cidr` → `cidr_block`. |
| `CloudSubnet` | Subnet | `zone` → Crusoe location. |
| `CloudSecurityGroup` | Security group | ingress/egress rules carried as dicts. |
| `CloudKeyPair` | SSH key | deduped by name. |
| `CloudImage` | image alias | `CrusoeResolver.image_to_alias`. |
| `CloudInstance` | VM | size / accelerators → `instance_type`. |
| `CloudInterconnect(INFINIBAND_*)` | IB partition + `ib_partition_id` | grouped by `placement_group` / interconnect kind. |
| `CloudStorageVolume` | Disk | attach-after-create. |
| `CloudObjectBucket` | unsupported | `validate`-error (no native object storage). |
| `CloudLoadBalancer` | unsupported | `validate`-error (no LB surface). |
| `CloudSharedFilesystem(VENUE_NATIVE, existing_id)` | storage-disk file-system | attach-only. |
| `VPNJoinSpec` | `user_data` cloud-init on launch | M6 renderer. |
| Tags | Crusoe labels dict | round-trip identity. |

## Idempotency

Reads filter by the `codecraftai-run-id` label.  IB partitions are checked by
name before create.  `instance_type` drift is reported as UPDATE-by-recreate
in `plan`.  `destroy` reverses apply order and de-registers VPN devices via
`IVPNControlPlane.delete_device`.

## Live runs

Live end-to-end runs are gated by `RUN_LIVE_CRUSOE=1` because GPU SKUs incur
per-second charges.
