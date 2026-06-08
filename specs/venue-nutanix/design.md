# Design — Nutanix AHV Provisioner

## Overview

`NutanixCloudProvisioner` realises the neutral resource model on Nutanix AHV
clusters via Prism Central.  All API calls go through
`codecraftai-interop-nutanix`'s `NutanixClient`, which wraps the Prism Central
v3/v4 REST APIs on `RestClientBase`.  Prism Central is the apex container;
clusters (UUIDs) are the placement targets.

Prism uses **Categories + Values** as its native tagging system; the
provisioner uses `codecraftai-run-id` as a Category Name and the run id string
as its Value, alongside one Category per neutral tag key.

See Also:
- [cloud-resource-model](../cloud-resource-model/design.md)
- [cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md)
- [vpn-join-spec](../vpn-join-spec/design.md)
- `codecraftai-interop-nutanix/Agents.md`

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    ProvisioningEngine                        │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              NutanixCloudProvisioner                         │
│  provisioning/venues/nutanix/nutanixcloudprovisioner.py      │
└────┬───────────────────┬────────────────────┬───────────────┘
     │                   │                    │
     ▼                   ▼                    ▼
┌─────────────┐  ┌──────────────────┐  ┌──────────────────────┐
│NtxResolver  │  │NtxCategoryTrans  │  │NtxCloudInitRenderer  │
│img/cluster  │  │ neutral↔cat/value│  │ base64 user_data     │
└─────────────┘  └──────────────────┘  └──────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│        NutanixClient (codecraftai-interop-nutanix)              │
│   vpcs / subnets / images / vms / categories / flow / tasks  │
│   RestClientBase against https://<pc>:9440/api/nutanix/v3    │
└──────────────────────────────────────────────────────────────┘
```

REST call paths used by `apply`:

- `POST /vpcs/list` / `POST /vpcs`
- `POST /subnets/list` / `POST /subnets`
- `POST /flow_network_security/rules/list` / `POST .../rules`
- `POST /images/list` (image verification)
- `POST /vms/list` / `POST /vms`
- `GET /tasks/{uuid}` (poll until `SUCCEEDED`)
- `POST /categories/{key}` / `PUT /categories/{key}/{value}`

---

## Mapping Table

| Neutral model | Nutanix primitive | Notes |
| --- | --- | --- |
| `apod` envelope | Prism Central + Cluster UUID | configured per run. |
| `CloudNetwork` | Flow VPC | optional — overlay-only VMs can sit directly on a Subnet. |
| `CloudSubnet` | Subnet (VLAN or VPC overlay) | `cidr` → `ip_config`. |
| `CloudSecurityGroup` | Flow Security Policy | rule sets keyed by SG name. |
| `CloudKeyPair` | injected into cloud-init user_data. |
| `CloudImage` | Image (`disk_image`) | resolver looks up by `name=` pattern. |
| `CloudInstance` | VM | `size` → vCPU/RAM/disk; cluster reference required. |
| `CloudInterconnect` | unsupported | `validate`-error. |
| `CloudStorageVolume` | additional disk on VM | thick/thin provisioning per `type`. |
| `CloudObjectBucket` | Nutanix Objects bucket (extension) or `validate`-error. |
| `CloudLoadBalancer` | unsupported | `validate`-error. |
| `CloudDnsRecord` | external | warn today. |
| `CloudSharedFilesystem(*, existing_id)` | Nutanix Files share mount | attach-only. |
| `VPNJoinSpec` | base64 `guest_customization.cloud_init.user_data`. |
| Tags | Categories+Values | round-trip identity. |

---

## Module Layout

```
source/packages/ccai/provisioning/venues/nutanix/
├── __init__.py
├── nutanixcloudprovisioner.py
├── ntxresolver.py
├── ntxcategorytranslator.py
├── ntxcloudinitrenderer.py
├── ntxplanbuilder.py
├── ntxapplystages.py
├── ntxdestroystages.py
├── ntxinventory.py
└── ntxerrors.py
```

---

## Idempotency

Lists are filtered by category-value pairs.  All mutating calls return an
`ergon` task; the provisioner polls `/tasks/{uuid}` until success with
`aspects.timeout_seconds`.  VM hardware drift uses in-place `PUT /vms/{uuid}`
where Prism permits.

---

## Testing Strategy

- `MockNutanixClient` returns deterministic Prism JSON including the task
  poll loop.
- Property tests: idempotent apply, inverse destroy, category/value
  round-trip identity.
- Validate-table tests confirm rejections.
- Live runs gated by `RUN_LIVE_NUTANIX=1` against a homelab Prism Central.
