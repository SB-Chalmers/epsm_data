"""Generate Fridhemsskolan sections with visible source/provisional labels."""

import argparse
import json
from pathlib import Path

from matplotlib import pyplot as plt

from epsm_data import Catalogue
from epsm_data.reporting.section_drawing import plot_sections


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("output/school_se02_sections"))
    args = parser.parse_args()
    reference = Catalogue.load().source_reference("school_fridhem")
    args.output.mkdir(parents=True, exist_ok=True)
    titles, tags = {}, {}
    for role, assembly in reference.report["assembly_evidence"].items():
        row = reference.report["elements"][role]
        if role == "WINDOW":
            titles[role] = "One Hus 1 system · U/SHGC reported\nVT and pane detail provisional"
            continue
        source = (
            f"Published U {row['source_u']:.3f}"
            if row["source_u"] is not None
            else "Provisional assembly"
        )
        titles[role] = (
            f"{source} · Nominal U {row['assembly_u']:.3f}\n{row['thickness_m'] * 1000:g} mm · LoD1 target {row['lod1_target_u']:.3f}"
        )
        tags[role] = [
            "S" if layer["evidence_status"] == "source_reported" else "P"
            for c in assembly["components"]
            for layer in c["layers"]
        ]
    fig = plot_sections(
        reference.archetype,
        show=False,
        ncols=3,
        dpi=180,
        figsize=(16.2, 9.6),
        title="Fridhemsskolan · School SE.02 · Published and provisional layers",
        subtitle="Hus 1/3 representative · PUB-611 student thesis (2017) · Draft; current LoD1 targets use PUB-003",
        boundary_details=reference.report["boundary_details"],
        panel_subtitles=titles,
        layer_tags=tags,
        role_notes={
            "EXT_WALL": "Four published layers; added wood cladding is provisional.",
            "ROOF": "Table/appendix order differs; physical orientation provisional.",
            "GROUND_FLOOR": "Depths reported; EPS properties and ground physics inferred.",
            "INT_WALL_NONLOADBEARING": "95 mm stud/wool zone is a selected hypothesis.",
            "INTERMEDIATE_FLOOR": "All depths inferred; cavity selected at 150 mm.",
            "WINDOW": "VT is provisional; solar transmittance is not VT.",
        },
        footer_notes=[
            "S  Source-reported depth   ·   P  Provisional depth   ·   Density, heat capacity and surfaces remain provisional for all layers.",
            "Published U, nominal layer U and unchanged LoD1 targets are separate (W/(m² K)); framing zones are numerical equivalents.",
            "One wall and one window. Hus 2 basement is an inactive hypothesis. School LoD2, full carbon, ground and simulation are not accepted.",
        ],
    )
    for ext in ("png", "svg"):
        target = args.output / f"school_se02_existing_sections.{ext}"
        fig.savefig(target, facecolor="white")
        print(target)
    plt.close(fig)
    for name, data in (
        ("school_se02_existing_layers", reference.to_dict()),
        ("school_se02_existing_nominal", reference.to_nominal_dict()),
    ):
        target = args.output / f"{name}.json"
        target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(target)


if __name__ == "__main__":
    main()
