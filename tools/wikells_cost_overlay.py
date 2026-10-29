"""Build a private renovation cost overlay from a Wikells Sektionsdata export.

Wikells prices are licensed. This tool only records which work items price which
measure; the overlay it writes holds the numbers and must stay outside the
repository. Load it with ``RenovationCatalogue.load(library, costs=path)``.

Run: python tools/wikells_cost_overlay.py EXPORT.xlsx OVERLAY.json
"""

import json
import statistics
import sys
from pathlib import Path

import openpyxl

PRICE_YEAR = 2026
DATABASE = "Wikells Sektionsdata ROT 2026-10-01"

# Measure-type or candidate keys -> (Wikells post code, Core driver, per-unit divisor).
ENVELOPE = {
    "insulate_wall": ("7.039", "element_area_m2"),
    "insulate_roof/TOP_FLOOR": ("9.032", "element_area_m2"),
    "insulate_roof/ROOF": ("11.024", "element_area_m2"),
    "insulate_basement/BASEMENT_WALL": ("6.005", "element_area_m2"),
    "insulate_basement/GROUND_FLOOR": ("4.022", "element_area_m2"),
    # Candidate-specific posts where the type default does not describe the work.
    "insulate_wall.interior_wood_fibre_70": ("7.029", "element_area_m2"),
    "insulate_wall.interior_stone_wool_70": ("7.029", "element_area_m2"),
    "insulate_basement.ceiling_stone_wool_100": ("9.028", "element_area_m2"),
}
PROXY_NOTES = {
    "insulate_wall.interior_wood_fibre_70": "Priced as interior mineral-wool lining; wood fibre not separately priced.",
    "insulate_roof/TOP_FLOOR": "Loose-fill attic insulation; cellulose and wood fibre priced as glass wool "
                               "(Wikells snedtak posts 11.020-11.022 differ by under 1 %).",
    "insulate_basement.ceiling_stone_wool_100": "Underside insulation of a floor over an unheated basement.",
}
WINDOW_STANDARD, WINDOW_LOW_ENERGY, WINDOW_REMOVAL = "16.029", "16.031", "16.001"
LOW_ENERGY_U = 0.85
VENTILATION_TERMINAL = "200x200 tallriksventil-al"


def measures(path):
    workbook = openpyxl.load_workbook(path, read_only=True)
    rows = list(workbook["Measures"].iter_rows(values_only=True))
    header = rows[0]
    posts = {row[header.index("Code")]: dict(zip(header, row)) for row in rows[1:]}
    prices = list(workbook["PriceList"].iter_rows(values_only=True))
    return posts, prices


def post_items(post, driver, *, divisor=1.0, label=None):
    """Split one post's unit price into material, labour, subcontractor and overhead."""
    source = f"{DATABASE} {post['Code']} {post['Measure']} ({post['Unit']})"
    description = label or post["Measure"]
    items = []
    for category, column in (("material", "Material_SEK"), ("labour", "Labour_SEK"),
                             ("subcontractor", "Subcontractor_SEK"), ("overhead", "Overhead_SEK")):
        value = (post[column] or 0.0) / divisor
        if value <= 0:
            continue
        item = {"category": category, "rate": round(value, 2), "driver": driver,
                "description": description, "source": source}
        if category == "labour":
            item["labour_hours"] = round((post["Labour_h"] or 0.0) / divisor, 4)
        items.append(item)
    return items


def estimate(items, *, missing=(), notes=()):
    return {"currency": "SEK", "price_year": PRICE_YEAR, "items": items,
            "coverage": "partial" if missing else "complete", "missing_scope": list(missing),
            "includes_vat": False, "source_references": [DATABASE], "notes": list(notes)}


def main(export, target):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from epsm_data import Catalogue, RenovationCatalogue

    posts, prices = measures(export)
    hourly = statistics.median(p["Labour_SEK"] / p["Labour_h"] for p in posts.values()
                               if p["Labour_h"] and p["Labour_SEK"])
    overlay = {}
    for key, (code, driver) in ENVELOPE.items():
        overlay[key] = estimate(post_items(posts[code], driver), notes=[
            "One representative work item per measure type and role; layer thicknesses of "
            "individual candidates are not re-priced.", *([PROXY_NOTES[key]] if key in PROXY_NOTES else [])])
    renovations = RenovationCatalogue.load(Catalogue.load())
    for candidate in renovations.filter("replace_window"):
        code = WINDOW_LOW_ENERGY if candidate.window.u_value <= LOW_ENERGY_U else WINDOW_STANDARD
        overlay[candidate.candidate_id] = estimate(
            post_items(posts[code], "window_count") + post_items(
                posts[WINDOW_REMOVAL], "window_count", label="Existing window removed"),
            notes=["Priced per 9x12 window unit; window_count uses the candidate's typical area."])
    header = prices[0]
    terminal = next(dict(zip(header, row)) for row in prices[1:]
                    if row[header.index("Benämning")] == VENTILATION_TERMINAL)
    def terminal_items(driver):
        return [
            {"category": "material", "rate": round(terminal["Material"], 2), "driver": driver,
             "description": "Air terminal, builder supply", "source": f"{DATABASE} price list ZSD {VENTILATION_TERMINAL}"},
            {"category": "labour", "rate": round(terminal["Tid"] * hourly, 2), "driver": driver,
             "labour_hours": terminal["Tid"], "description": "Air terminal, builder fitting",
             "source": f"{DATABASE} price list ZSD; labour at the median implied rate {hourly:.0f} SEK/h"}]
    overlay["upgrade_ventilation"] = estimate(
        terminal_items("supply_terminal_count") + terminal_items("exhaust_terminal_count"),
        missing=("air handling units and fans", "ductwork supply and installation",
                 "controls, commissioning and builder's work in shafts"),
        notes=["Wikells ROT prices ventilation installation as a zero subcontractor placeholder "
               "(20.004 LUFT); only builder-side terminals are priced."])
    Path(target).write_text(json.dumps({"source": DATABASE, "costs": overlay}, indent=2,
                                       ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(overlay)} cost estimates -> {target}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
