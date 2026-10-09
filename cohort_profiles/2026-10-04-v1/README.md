# Gothenburg MF SE.02 effective cohort profile v1

This separate resource uses EPSM reference database v1.4. It contains inferred
shared physical assumptions from the completed 85-building/54-property retrospective
validation. Profile status: ['provisional']. The source export SHA-256 is `65e1cc6378caab61dfb66ca9b7484ede74590432b6236b43c0f8cbfa60c08ed0`.
Exact full-data refit coefficients are not independently validated; property folds
validate the fitting procedure. Construction-reference assemblies remain authoritative.

Read this JSON and pass a bundle and target-free descriptors to
`epsm_data.cohorts.assign_cohort`, then apply the returned profile with
`apply_cohort_profile(spec, profile, locked_parameters=...)`. Include municipality
1480 in the descriptors. Other or missing municipalities fall back to the parent.
Provisional profiles require `allow_provisional=True`; default assignment retains
the reference parent when support is insufficient. Protect independently evidenced
component inputs through the documented locks. Never put heating targets or residuals
into assignment descriptors.

Calibration assumptions and bounds do not establish measured leakage, renovation
state, window performance, occupancy or basement conditioned extent. Completed
window-measure flags provide no measured U-value. The full assessment, sensitivity
atlas, per-building misses, numerical failures and source archive are retained in
EPSM Workflows `cohort-transfer-mf-se02-parent-2026-10-04-v10` and `archetype-parent-validation-2026-10-04-v2`. Other Swedish matrix cells
remain subject to their own physical validation campaigns.

## Superseded on 2026-10-05

The Data 1.5 rerun selected the unchanged baseline. Use
[the current v2 profile](../2026-10-05-v2/README.md) with the Atemp-area infiltration
basis. This historical profile belongs to the previous ACH basis and must not be
stacked onto Data 1.5 inputs. The historical artifact is retained for provenance.
