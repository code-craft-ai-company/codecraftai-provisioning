# Nebius Cloud Venue

`NebiusCloudProvisioner` realises the neutral provisioning resource model on
the Nebius IaaS GPU cloud.  Nebius offers conventional IaaS primitives plus
InfiniBand-enabled placement groups (GPU Clusters) and a native shared
filesystem service suited to distributed-training workloads.

## Cross-references

- Neutral resource model — [`cloud-resource-model`](../../../../../../specs/cloud-resource-model/design.md)
- Provisioner lifecycle — [`cloud-provisioner-lifecycle`](../../../../../../specs/cloud-provisioner-lifecycle/design.md)
- VPN cloud-init injection — [`vpn-join-spec`](../../../../../../specs/vpn-join-spec/design.md)
- Nebius REST client — `codecraftai-interop-nebius` (`ccai.restclient.nebius.NebiusClient`)

## Mapping table

| Neutral model | Nebius primitive | Notes |
| --- | --- | --- |
| `NebiusSpec.parent_id` | project / folder | the apex parent id anchoring every resource. |
| `CloudNetwork` | VPC | `cidr` → `ipv4_cidr_block`. |
| `CloudSubnet` | subnet | `zone` → `zone_id`. |
| `CloudSecurityGroup` | security group | rule sets. |
| `CloudKeyPair` | SSH key | registered idempotently by name. |
| `CloudImage` | image id | resolver maps `family/version/arch`. |
| `CloudInstance` | VM | `size`/`accelerators` → preset slug; GPU SKU via the accelerator catalog. |
| `CloudInterconnect(INFINIBAND_*)` | GPU Cluster (IB-enabled placement group) | grouped by `placement_group`. |
| `CloudStorageVolume` | disk | attach-after-create. |
| `CloudSharedFilesystem(existing_id)` | native shared filesystem | attach-only in v1 — mount targets per subnet. |
| `CloudObjectBucket` | — | rejected at validate (no v1 client surface). |
| `CloudLoadBalancer` | — | rejected at validate (unsupported in v1). |
| `CloudDnsRecord` | — | deferred to v1.5 — emitted as a SKIP in plan. |
| `VPNJoinSpec` | `metadata["user-data"]` | M6 `render_cloud_init` cloud-init document. |
| Tags | Nebius labels dict | round-trip identity for conformant inputs. |

## Lifecycle

- **validate** — anchors every resource to a `parent_id`, enforces
  subnet/network CIDR containment, rejects load balancers, object buckets,
  and provision-intent shared filesystems, and checks IB-platform
  eligibility for InfiniBand interconnects.
- **plan** — lists resources filtered by the `codecraftai-run-id` label and
  emits CREATE / SKIP / UPDATE-by-recreate actions.
- **apply** — VPC → Subnet → Security Group → SSH keys → GPU Cluster →
  Instances → Disks → File-storage attach.  Idempotent: a re-apply makes no
  mutating create calls.  UPDATE-by-recreate actions are gated on
  `aspects.confirm`.
- **destroy** — reverses the apply order and invokes
  `IVPNControlPlane.delete_device` for every VPN-joined instance.
- **inventory** — enumerates run-id-labelled resources as
  `ProvisionedResource` records; the apply inventory is persisted under
  `.output/provisioning/<runid>/nebius-inventory.json`.

## Live integration tests

The example-based and property tests run against an in-memory
`MockNebiusClient`.  Live runs are gated by the `RUN_LIVE_NEBIUS=1`
environment variable.
