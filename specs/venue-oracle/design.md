# Design — Oracle Cloud Infrastructure Provisioner

## Overview

`OracleCloudProvisioner` realises the neutral resource model on OCI via the `oci`
SDK surfaced by `codecraftai-interop-oracle`.  OCI's structural specialties are
**compartments** (the apex container, hierarchical), **availability domains**
(per-region zones), and **cluster networks** (the RoCEv2 RDMA fabric for HPC).
This provisioner treats the compartment OCID as the apex container and uses the
`codecraftai-run-id` freeform tag as the per-run discriminator.

See Also:
- [cloud-resource-model](../cloud-resource-model/design.md)
- [cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md)
- [vpn-join-spec](../vpn-join-spec/design.md)
- [oracle-credentials](../../../codecraftai-credentials/specs/oracle-credentials/design.md)
- `codecraftai-interop-oracle/Agents.md`

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    ProvisioningEngine                        │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              OracleCloudProvisioner                          │
│  provisioning/venues/oracle/oraclecloudprovisioner.py        │
└────┬──────────────────┬───────────────────┬─────────────────┘
     │                  │                   │
     ▼                  ▼                   ▼
┌─────────────┐  ┌────────────────┐  ┌──────────────────────┐
│OciResolver  │  │OciTagTrans     │  │OciUserDataRenderer   │
│shape/img/ad │  │ neutral↔freeform│  │ metadata user_data  │
└─────────────┘  └────────────────┘  └──────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│        OciClient (codecraftai-interop-oracle)                   │
│   core(VCN/Subnet/Compute/Volume) / object-storage / dns /   │
│   file-storage / cluster-network  oci SDK                    │
└──────────────────────────────────────────────────────────────┘
```

SDK call paths used by `apply`:

- `VirtualNetworkClient.list_vcns` / `create_vcn`
- `VirtualNetworkClient.list_subnets` / `create_subnet`
- `VirtualNetworkClient.list_security_lists` / `create_security_list`
- `ComputeManagementClient.list_cluster_networks` / `create_cluster_network`
- `ComputeClient.list_instances` / `launch_instance` with `metadata.user_data`
- `BlockstorageClient.list_volumes` / `create_volume` / `attach_volume`
- `FileStorageClient.list_mount_targets` / `create_mount_target`
- `ObjectStorageClient.head_bucket` / `create_bucket`
- `DnsClient.list_zones` / `update_rr_set`

---

## Mapping Table

| Neutral model | OCI resource | Notes |
| --- | --- | --- |
| `apod` envelope | Compartment OCID | configured per run; not created by the provisioner. |
| `CloudNetwork` | VCN | `cidr` → `cidr_blocks`. |
| `CloudSubnet` | Subnet | `zone` → availability domain. |
| `CloudSecurityGroup` | Security List (preferred) or NSG | NSG path opt-in via spec hint. |
| `CloudKeyPair` | injected into `metadata["ssh_authorized_keys"]` | no first-class key resource. |
| `CloudImage` | image OCID | resolved via `compute.list_images(...)` by family/version. |
| `CloudInstance` | Compute Instance | `size` → shape (`VM.Standard.E4.Flex`, `BM.GPU.H100.8`). |
| `CloudInstance.accelerators` | BM.GPU shapes | resolved per catalog. |
| `CloudInterconnect(OCI_RDMA, ...)` | Cluster Network | groups instances sharing `interconnect_group`. |
| `CloudStorageVolume` | Block Volume | attach-after-create. |
| `CloudObjectBucket` | Object Storage bucket | namespace-scoped. |
| `CloudLoadBalancer` | LB (v1.5 stub) | warn today. |
| `CloudDnsRecord` | DNS RRSet | zone resolved by name. |
| `CloudSharedFilesystem(VENUE_NATIVE)` | File Storage Mount Target + Export | NFSv3. |
| `CloudSharedFilesystem(LUSTRE, existing_id)` | Managed Lustre attach | `existing_id` required. |
| `VPNJoinSpec` | base64 `metadata["user_data"]` | identical to AWS. |
| Tags | Freeform Tags (`Dict[str,str]`) | round-trip identity. |

---

## Module Layout

```
source/packages/ccai/provisioning/venues/oracle/
├── __init__.py
├── oraclecloudprovisioner.py
├── ociresolver.py
├── ocitagtranslator.py
├── ociuserdatarenderer.py
├── ociplanbuilder.py
├── ociapplystages.py
├── ociclusternetwork.py        # RDMA cluster network helper
├── ocidestroystages.py
├── ociinventory.py
└── ocierrors.py
```

---

## Idempotency

Reads are compartment-scoped list calls filtered by freeform tag.  Cluster
networks are immutable in topology; topology drift forces UPDATE-by-recreate
gated on `aspects.confirm`.

---

## Testing Strategy

- `MockOciClient` per service.
- Property tests: idempotent apply, inverse destroy, freeform-tag round-trip
  identity.
- Cluster-network grouping test: N RDMA instances sharing `interconnect_group`
  yield one cluster network with N members.
- Validate-table tests confirm EFA / INFINIBAND_* / WEKA rejections.
- Live runs gated by `RUN_LIVE_OCI=1`.
