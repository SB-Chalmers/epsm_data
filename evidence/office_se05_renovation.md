# Office SE.05: representative renovation changes

One office archetype should hold Existing, Standard and Advanced state records.
Each state has exactly one EXT_WALL and one WINDOW. Replacement windows are
single whole-window systems; no facade-specific types or geometry are exported.
Existing is accepted now. Renovation recipes are proposals, not implemented or
accepted construction states. LoD1 renovation targets are existing catalogue
assumptions rather than renovated assemblies specified by the Poirazis thesis.

## Nominal changes needed against unchanged LoD1

These practical candidate depths keep source conductivities and all other
representative layers fixed. Wall/roof wool uses lambda=0.036 W/(m K); floor EPS
uses 0.035. U uses the same fixed EPSM films as Existing. Depths shown are total
insulation depth; additions are measured from the calibrated Existing stack.

| Element | Existing | Standard candidate / target | Advanced candidate / target |
|---|---|---|---|
| External wall wool | 90 mm; U=0.308862 | 130 mm (+40); U=0.229948 / target 0.228381 | 260 mm (+170); U=0.125630 / target 0.125000 |
| Roof wool | 165 mm; U=0.188145 | 295 mm (+130); U=0.112030 / target 0.111587 | 335 mm (+170); U=0.099629 / target 0.100000 |
| Ground-floor EPS | 100 mm; U=0.322373 | 125 mm (+25); U=0.262035 / target 0.260309 | 130 mm (+30); U=0.252580 / target 0.254377 |
| Representative window | U=1.988293 | Replace with one U=1.000000 system | Same U=1.000000 target; one system |
| Infiltration | 0.20 h^-1 | Retain 0.20 h^-1 | Airtightness improvement to 0.05 h^-1 |

All proposed opaque values above are within 2% of the current LoD1 targets.
They are feasible nominal starting points. Final bounded search must use the
chosen construction/product thickness grid and report the selected changes;
these preliminary depths are not assertions about the smallest passing grid
candidate. Use R_new = 1/U_existing + added_depth/lambda to reproduce the check.

Keep the 160 mm intermediate slab, internal partition, their thermal targets,
and all unchanged layers. Neither state compounds onto the other: derive both
directly from Existing. No basement is present in this source building, so the
LoD1 basement proxy does not justify adding a basement assembly.

## Construction decisions and evidence needed

- More wall insulation needs a representative facade intervention: replace or
  rebuild the relevant facade build-up while preserving/recording brick and
  internal layers. A numerical increase of the wool layer is an equivalent
  projection; it does not establish framing geometry or a buildable detail.
- Roof insulation growth needs membrane removal/reinstatement and edge/fixing
  details. Preserve original concrete and acoustic layers in the numerical stack.
- More EPS below the ground slab implies disruptive floor/slab work. Review that
  intervention explicitly; a LoD1 floor improvement does not establish accessible
  under-slab space. Track removal and reinstatement instead of silently adding
  depth to an inaccessible assembly.
- Select an independently evidenced replacement window's SHGC and VT. U=1.0
  alone does not determine optics. Standard and Advanced can reuse one reviewed
  replacement product because their window targets coincide.
- Advanced airtightness is a separate building-level input, not a material layer.
  Store the 0.05 h^-1 target alongside the construction state. Preserve ventilation
  classifications; do not equate infiltration reduction with a system change.

## Implementation work remaining

1. Add Standard/Advanced beneath the existing `office_se05` archetype with
   captured LoD1 targets, an Existing revision link, reviewed interventions and
   practical depth choices. Keep one window material/assembly per state; a shared
   replacement product may be referenced by both renovated states.
2. Extend the office loader/CLI to select renovation_state and build each state
   from Existing. The generic detailed validator currently restricts office to
   Existing; its renovation input/builder currently serves MF only. Extend these
   paths without weakening existing MF validation or changing its revisions.
3. Extend nominal role validation from office Existing to both office renovation
   states using the same six roles. Preserve evidence and changed mass/capacity;
   distinguish retained, added, replaced and reinstated material in reports/plots.
4. Compute per-state export and acceptance checks across all 12 classification
   slots. Acceptance would increase from 48 to 72 slots only when both renovated
   states pass, including optics/product evidence and captured-target stability.
5. Keep ground-validation, complete-carbon and full-simulation readiness separate.
   Existing source plenum and surrogate-product qualifications still apply.

[Existing representative evidence](poirazis_2008_office_building.md)
