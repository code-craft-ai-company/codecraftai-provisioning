# Design — AWS Cloud Provisioner

## Overview

`AwsCloudProvisioner` is a concrete `CloudProvisioner` that maps the neutral resource
model onto AWS via `boto3`.  It is the largest and most exercised venue and serves as
the reference shape every other venue follows.  All AWS calls go through
`automojo-interop-aws`'s `AwsClient`, which owns the `boto3.Session` and exposes
service-scoped sub-clients (`ec2`, `s3`, `route53`, `fsx`).  This module owns no HTTP
or AWS session state of its own.

The provisioner follows the §2.7.3 pipeline: validate → plan → apply networking →
apply compute → apply DNS/object/LB → bootstrap VPN → verify → emit inventory.  Every
mutating step is preceded by a read-before-create check on a deterministic resource
key derived from the spec name plus the `automojo-run-id` tag.

See Also:
- [cloud-resource-model](../cloud-resource-model/design.md)
- [cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md)
- [vpn-join-spec](../vpn-join-spec/design.md)
- `automojo-interop-aws/Agents.md`

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│           ProvisioningEngine (provisioning-engine-pipeline)  │
└──────────────────────────┬───────────────────────────────────┘
                           │ validate / plan / apply / destroy
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                  AwsCloudProvisioner                         │
│  provisioning/venues/aws/awscloudprovisioner.py              │
│                                                              │
│  validate()  plan()  apply()  destroy()  inventory()         │
└────┬──────────────────┬───────────────────┬─────────────────┘
     │                  │                   │
     ▼                  ▼                   ▼
┌─────────────┐ ┌────────────────┐  ┌──────────────────────┐
│ AwsResolver │ │ AwsTagTranslator│  │ AwsCloudInitRenderer │
│ image→AMI    │ │ neutral↔Tags    │  │ user_data + vpn_join │
│ size→type    │ │                 │  │                      │
│ accel→family │ │                 │  │                      │
└─────────────┘ └────────────────┘  └──────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                AwsClient (automojo-interop-aws)              │
│   ec2 / s3 / route53 / fsx / efa  REST/SDK calls             │
└──────────────────────────────────────────────────────────────┘
```

REST/SDK call paths used by `apply`:

- `ec2.describe_vpcs`            → read-before-create for `CloudNetwork`
- `ec2.create_vpc`               → realise `CloudNetwork`
- `ec2.describe_subnets`         → read-before-create for `CloudSubnet`
- `ec2.create_subnet`
- `ec2.describe_security_groups` → read-before-create for `CloudSecurityGroup`
- `ec2.create_security_group` + `authorize_security_group_ingress`/`egress`
- `ec2.describe_key_pairs`       → read-before-create for `CloudKeyPair`
- `ec2.import_key_pair`
- `ec2.describe_images`          → image-family → AMI id (via `AwsResolver`)
- `ec2.describe_instances`       → read-before-create for `CloudInstance`
- `ec2.run_instances`            → with `Placement.GroupName` when EFA requested
- `ec2.create_placement_group`   → cluster strategy for EFA
- `ec2.create_network_interface` → EFA-enabled ENI when interconnect=EFA
- `ec2.create_volume` / `attach_volume`
- `s3.head_bucket` / `create_bucket`
- `route53.list_resource_record_sets` / `change_resource_record_sets`
- `fsx.describe_file_systems`    → attach FSx for Lustre by `existing_id`

---

## Mapping Table

| Neutral model | AWS resource | Notes |
| --- | --- | --- |
| `CloudNetwork` | VPC | `cidr` → `CidrBlock`; tagged with `automojo-run-id`. |
| `CloudSubnet` | Subnet + (if `public=True`) IGW + route | One route table per public subnet group. |
| `CloudSecurityGroup` | SG | `ingress_rules` → `authorize_security_group_ingress`. |
| `CloudKeyPair` | EC2 KeyPair (imported) | `public_key_material` → `import_key_pair`. |
| `CloudImage` | AMI id | Resolved via `AwsResolver.image_to_ami(family, version, arch)`. |
| `CloudInstance` | EC2 Instance | `size` → `InstanceType`; `subnet` → `SubnetId`; `vpn_join` → cloud-init in `user_data`. |
| `CloudInstance.accelerators` | GPU instance family | `H100_SXM × 8` → `p5.48xlarge`; `H200_NVL × 8` → `p5e.48xlarge`. |
| `CloudInterconnect(EFA, RAIL_OPTIMIZED)` | Cluster placement group + EFA ENI | Validated against instance-family EFA support. |
| `CloudStorageVolume` | EBS volume | `type` → `gp3`/`io2`/`st1`. |
| `CloudObjectBucket` | S3 bucket | Region required. |
| `CloudLoadBalancer` | ALB/NLB (v1.5 stub) | `validate`-errors today. |
| `CloudDnsRecord` | Route53 record set | Hosted zone resolved by `zone_name`. |
| `CloudSharedFilesystem(LUSTRE)` | FSx for Lustre | Attach-only in v1. |
| `CloudSharedFilesystem(WEKA)` | unsupported | `validate`-error. |
| `VPNJoinSpec` | cloud-init `runcmd` in `user_data` | Identical to other venues. |
| Tags | EC2 `Tags` (`{"Key":..,"Value":..}`) | Round-trip identity required. |

---

## Module Layout

```
source/packages/automojo/provisioning/venues/aws/
├── __init__.py
├── awscloudprovisioner.py        # AwsCloudProvisioner (validate/plan/apply/destroy/inventory)
├── awsresolver.py                # image/size/accelerator → AWS identifiers
├── awstagtranslator.py           # neutral tags ↔ AWS Tags (round-trip identity)
├── awscloudinitrenderer.py       # user_data + vpn_join injection
├── awsplanbuilder.py             # plan() implementation; emits PlanAction list
├── awsapplystages.py             # network / compute / dns stage executors
├── awsdestroystages.py           # reverse-order destroy
├── awsinventory.py               # inventory() — tag-scoped enumeration
└── awserrors.py                  # AwsValidationError, AwsConflictError, AwsCapacityError
```

---

## Data Models

The neutral types come from [cloud-resource-model](../cloud-resource-model/design.md).
AWS-specific result types:

```python
@dataclass
class AwsApplyResult:
    run_id: str
    created: list[ProvisionedResource]
    updated: list[ProvisionedResource]
    skipped: list[ProvisionedResource]
    failed: list[ProvisioningError]
```

---

## Idempotency

Every mutating call is preceded by a `describe_*` query keyed on:

- the spec's `automojo-run-id` tag (`apod` + run hash)
- the resource's spec `name` (mapped to a `Name` tag for searchability)

If the resource exists and its mutable attributes match the spec, the action is
`SKIP`.  If it exists with attribute drift, the action is `UPDATE` and only the
drifting attributes are patched.  If it does not exist, the action is `CREATE`.

`apply` and `destroy` are both safe to re-run — re-applying a fully-applied spec is a
no-op proven by the property test in `tasks.md`.

---

## Testing Strategy

- Unit tests stub `AwsClient` with a `MockAwsClient` whose `describe_*` methods drive
  the read-before-create branches.
- Tag round-trip identity is property-tested with `hypothesis`.
- Idempotent apply is property-tested: generate a spec, apply against a mock account,
  re-apply, assert no mutating calls.
- Inverse destroy property test: apply then destroy must leave the mock account
  empty.
- GPU SKU resolution is table-driven against the accelerator catalog YAML.
- EFA validation table: each EFA-supported family is asserted positive, each
  non-EFA family is asserted negative.
- Live AWS calls live behind a `RUN_LIVE_AWS=1` env gate and are excluded from CI.
