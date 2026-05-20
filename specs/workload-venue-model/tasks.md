# Implementation Plan — Workload Venue Model

## Enum + Data Classes

- [x] 1. Create `workloadvenuekind.py` — locked enum with 4 values
- [x] 2. Create `workloadvenue.py` — `WorkloadVenue(SchemaObject)`
- [x] 3. Create `nodepoolspec.py` — `NodePoolSpec(SchemaObject)`
- [x] 4. Create `autoscalingspec.py` — `AutoscalingSpec(SchemaObject)`
- [x] 5. Create `workloadcluster.py` — `WorkloadCluster(SchemaObject)`
- [x] 6. Create `workloadjob.py` — `WorkloadJob(SchemaObject)`
- [x] 7. Create `workloadservice.py` — `WorkloadService(SchemaObject)`

## Abstract Base

- [x] 8. Create `workloadprovisioner.py` — abstract base with 5 verbs
- [x] 9. Constructor accepts optional `cloud_provisioner` for composition
- [x] 10. Every method requires named `aspects: Aspects` parameter

## V1 Subclasses (stubs)

- [ ] 11. Create `kubernetesworkloadprovisioner.py` — full v1 impl shell
- [ ] 12. Create `slurmworkloadprovisioner.py` — `apply` raises NIE
- [ ] 13. Create `rayworkloadprovisioner.py` — `apply` raises NIE
- [ ] 14. Create `nomadworkloadprovisioner.py` — `apply` raises NIE
- [ ] 15. NIE messages include a stable issue-tracker pointer

## Validation Hooks

- [ ] 16. Resolve `credential_ref` from vault during validate
- [ ] 17. Verify credential type matches `kind`
- [ ] 18. Validate node-pool accelerators against catalog + venue capability matrix
- [ ] 19. Reject `LoadBalancer` exposure on venues without LB support

## Tests — Examples

- [x] 20. `test_workload_venue_kind_enum_locked`
- [x] 21. `test_workload_venue_roundtrip`
- [x] 22. `test_workload_job_rejects_zero_replicas`
- [x] 23. `test_workload_cluster_with_node_pools_roundtrip`
- [ ] 24. `test_workload_service_loadbalancer_exposure_validates`
- [ ] 25. `test_slurm_provisioner_apply_raises_nie`
- [ ] 26. `test_ray_provisioner_apply_raises_nie`
- [ ] 27. `test_nomad_provisioner_apply_raises_nie`
- [ ] 28. `test_composition_drives_cloud_before_workload`
- [ ] 29. `test_node_pool_accelerator_rejected_when_unsupported`

## Documentation

- [ ] 30. Document the §7.6 ECS/ACI/Cloud Run exclusion in module docstring
- [ ] 31. Cross-link to `automojo-interop-kubernetes`
