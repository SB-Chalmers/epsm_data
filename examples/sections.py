"""Draw the accepted MF SE.02 LoD2 fabric alternatives.

Run: python -m examples.sections --output output/mf_se02_sections
Requires the visualization extra.
"""

import argparse
from pathlib import Path

from matplotlib import pyplot as plt

from epsm_data import Catalogue
from epsm_data.reporting.section_drawing import plot_sections, section_scales


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("output/mf_se02_sections"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    catalogue = Catalogue.load()
    states = {
        state: catalogue.get("mf_se02", state=state)
        for state in ("existing", "standard", "advanced")
    }
    scales = section_scales(list(states.values()))
    for state, archetype in states.items():
        figure = plot_sections(
            archetype, show=False, dpi=180, title=f"MF SE.02 · {state.title()}", scales=scales
        )
        for extension in ("png", "svg"):
            target = args.output / f"mf_se02_{state}_sections.{extension}"
            figure.savefig(target, facecolor="white")
            print(target)
        plt.close(figure)


if __name__ == "__main__":
    main()
