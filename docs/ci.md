# Continuous integration

Pull requests into `dev` and `main` run offline library checks with the base
`dev` dependencies. The development gate runs Ruff, the full pytest suite and a
wheel build. Tests for optional visualization and geographic preparation skip
when their extras are absent. Catalogue selection and ordinary climate lookup
remain part of the dependency-free checks.

The manual release gate verifies the supported Python versions with
`visualization` and `geography`, builds distributions and checks the installed
wheel from outside the checkout. Use it before publishing and when changing
optional-package behavior.

The executable configuration is in
[development checks](../.github/workflows/ci.yml) and
[release verification](../.github/workflows/tests.yml). Preserve the exact tested
source revisions and investigate failed checks before rerunning them. Data's
suite validates this library; integration studies retain their own dependency
cohort and engine results.
