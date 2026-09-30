"""Render MF SE.02 overview sheets and aligned construction comparisons.

Run: python -m examples.sections [--output output/mf_se02_sections]
"""

import argparse
from pathlib import Path

from matplotlib import pyplot as plt

from epsm_data import load_calibrated_archetype
from epsm_data.reporting.section_drawing import (
    plot_section_comparison,
    plot_sections,
    renovation_annotations,
    section_scales,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("output/mf_se02_sections"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    states = [
        load_calibrated_archetype(renovation_state=s) for s in ("existing", "standard", "advanced")
    ]
    scales = section_scales(
        [s.archetype for s in states], [s.report["boundary_details"] for s in states]
    )

    def save(fig, name):
        for extension in ("png", "svg"):
            target = args.output / f"{name}.{extension}"
            fig.savefig(target, facecolor="white")
            print(target)
        plt.close(fig)

    for calibrated in states:
        state = calibrated.report["key"]["renovation_state"]
        tags, notes = renovation_annotations(calibrated, states[0])
        fig = plot_sections(
            calibrated.archetype,
            show=False,
            dpi=180,
            title=f"MF SE.02 · {state.title()}",
            boundary_details=calibrated.report["boundary_details"],
            scales=scales,
            layer_tags=tags,
            role_notes=notes,
        )
        save(fig, f"mf_se02_{state}_sections")
    for role, name in (
        ("EXT_WALL", "external_wall"),
        ("TOP_FLOOR", "attic_floor"),
        ("GROUND_FLOOR", "ground_floor"),
        ("BASEMENT_WALL", "basement_wall"),
        ("WINDOW", "window"),
    ):
        fig = plot_section_comparison(states, role, show=False)
        save(fig, f"mf_se02_{name}_comparison")


if __name__ == "__main__":
    main()
