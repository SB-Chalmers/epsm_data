# Sourced material-grade expectations

These fixtures specify independently sourced material-grade choices and their
explicit forward-calculation assumptions. They are reviewed expectations, not
snapshots regenerated to make a catalogue pass.

`mf_se01_aac.json` records the BABS 1946 500 kg/m³ lightweight-concrete masonry
grade, its SI conversion, the retained 250 mm wall composition, the modern
Boverket AAC carbon proxy and the unchanged TABULA baseline comparison. The
masonry conductivity already accounts for mortar. Boverket’s representative
400 kg/m³ conversion remains distinct from the historic 500 kg/m³ thermal grade;
the resulting 25% density difference must remain visible as a review finding.
A5.1 remains a known partial module and does not establish complete A5.

The MF SE.01 wall regression retains the sourced historic AAC grade in each
state. Renovated walls add the separately sourced TABULA 50/300 mm insulation
and 120 mm brick facing; their resistance is calculated forward. Detailed
renovation package expectations are kept in
`../catalogue_sanity/cases/mf_se01_renovation.json`.
