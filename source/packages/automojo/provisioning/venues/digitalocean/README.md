# DigitalOcean Provisioning Venue

`DigitalOceanCloudProvisioner` realises the venue-neutral cloud resource model
on DigitalOcean.  It is a concrete subclass of the M6
[`CloudProvisioner`](../../model/cloud/cloudprovisioner.py) base and implements
the five-verb lifecycle: `validate`, `plan`, `apply`, `destroy`, `inventory`.

DigitalOcean is intentionally lower-feature than the hyperscalers.  The venue
is honest in `validate` about asks it cannot realise (WEKA/Lustre-class shared
filesystems, HPC cluster interconnects) and rejects them with substitution
guidance rather than failing late at apply time.

## SDK usage

The venue uses the `pydo` SDK directly through the thin `DigitalOceanClient`
wrapper — there is no separate interop package (the same pattern the AWS venue
uses with `boto3`).  `pydo` is imported lazily so the package imports cleanly
even when the SDK is not installed; tests inject a fully in-memory mock client
and never touch the DigitalOcean API.

## Mapping table

| Neutral model            | DigitalOcean resource        |
| ------------------------ | ---------------------------- |
| `CloudNetwork`           | VPC                          |
| `CloudSubnet`            | folded into VPC (tag-only)   |
| `CloudSecurityGroup`     | Cloud Firewall               |
| `CloudKeyPair`           | account-scoped SSH key       |
| `CloudImage`             | image slug                   |
| `CloudInstance`          | Droplet                      |
| `CloudInstance.accelerators` | GPU Droplet (`gpu-h100x*`) |
| `CloudInterconnect`      | unsupported (validate-error) |
| `CloudStorageVolume`     | Block Storage volume         |
| `CloudObjectBucket`      | Spaces bucket                |
| `CloudLoadBalancer`      | DO Load Balancer (v1.5 stub) |
| `CloudDnsRecord`         | DO DNS record                |
| `CloudSharedFilesystem`  | unsupported (validate-error) |
| `VPNJoinSpec`            | cloud-init via Droplet `user_data` |
| Tags                     | escaped `key=value` string list    |

## Idempotency

Read-before-create is keyed off the owner / run-id / resource-name tag triple.
Droplets, firewalls and volumes carry these tags natively; VPCs encode them in
the `description` field; SSH keys are deduped by fingerprint; Spaces buckets
use a run-scoped naming convention.  Droplet size changes are
UPDATE-by-recreate, gated on `aspects.confirm`.

## VPN join

When a `CloudInstance` carries a `vpn_join` spec the `DoUserDataRenderer`
delegates to the shared M6
[`render_cloud_init`](../../cloudinit/vpncloudinitrenderer.py) so the
Tailscale / Twingate bootstrap is identical to every other venue.  On
`destroy`, terminated VPN-joined Droplets trigger `IVPNControlPlane.delete_device`.

## See also

- [cloud-resource-model](../../../../../../specs/cloud-resource-model/design.md)
- [cloud-provisioner-lifecycle](../../../../../../specs/cloud-provisioner-lifecycle/design.md)
- [vpn-join-spec](../../../../../../specs/vpn-join-spec/design.md)
