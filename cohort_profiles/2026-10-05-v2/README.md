# Gothenburg MF SE.02 Data 1.5 profile v2

Current result of the completed 85-building / 54-property retrospective property
cross-validation. The final selection retains the Data 1.5 baseline and contains
no fitted parameter overrides. Additional infiltration remains 0.20 L/s/m² Atemp
and whole-window U remains 2.2 W/(m² K). Status is **provisional**: the accuracy
target was not met and no independent national validation is claimed.

The final baseline export achieves 54/85 within 20%, 37/85 within 10%, MAE 14.302
kWh/m²/year and signed bias +4.079. The fold-dependent selection procedure achieves
55/85 and 40/85; those procedure scores are not the final baseline export's scores.
Two rejected simulations remain in both coverage denominators.

Use this version in place of `../2026-10-04-v1/mf-se02-gothenburg.json`, which was
fitted on the previous ACH basis. Read `mf-se02-gothenburg.json` and pass the bundle
to `epsm_data.cohorts.assign_cohort` with target-free descriptors, including
municipality 1480. Default assignment falls back to the parent because support is
provisional. Explicit `allow_provisional=True` can assign the profile within
support; applying its empty overrides retains the baseline. Protect independently
evidenced inputs with the documented locks. Never use heating targets/residuals
as assignment descriptors.

The source export checksum and reference locators are retained in the JSON.
See ../../docs/mf-se02-data15-validation.md and the packaged evidence record.
Other locations, uses, eras, renovation states and ventilation/heating systems
require their own validation.
