"""Build all 13 BETSI multifamily archetypes and validate U-values.

Material mapping (BETSI → Honeybee × Boverket):
  brick          → M01 100mm brick (k=0.89)              × 6000000082
  concrete       → 4 in. Normalweight Concrete Wall      × 6000000026
  lw_concrete    → M11 100mm lightweight concrete (k=0.53) × 6000000085
  mw_old         → Mineral Wool Old (created) (k=0.042)  × 6000000123
  mw_new         → Mineral Wool New (created) (k=0.036)  × 6000000123
  gypsum         → G01 13mm gypsum board (k=0.16)        × 6000000020
  plaster        → 25mm Stucco (k=0.72)                  × 6000000020
  wood           → G05 25mm wood (k=0.15)                × 6000000007
  plywood        → 5/8 in. Plywood (k=0.12)              × 6000000023
  eps            → I02 50mm insulation board (k=0.03)    × 6000000131
  roof_membrane  → Built-up Roofing (k=0.16)             × 6000000132
  concrete_floor → 100mm Normalweight concrete floor     × 6000000026
  concrete_roof  → 6 in. Heavyweight Concrete Roof       × 6000000026
  conc_block_bsmt→ 8 in. Concrete Block Basement Wall    × 6000000026

Target median U-values from BETSI (W/m²K):
  Masonry:         wall=0.51, roof=0.25, floor=0.31, win=2.50, bwall=0.85
  Concrete walls:  wall=0.22, roof=0.14, floor=0.27, win=1.90, bwall=0.42
  All-concrete:    wall=0.30, roof=0.14, floor=0.23, win=1.90, bwall=0.64
  Timber frame:    wall=0.19, roof=0.14, floor=0.25, win=2.00, bwall=0.81
"""
import json
import logging
from pathlib import Path

logging.disable(logging.WARNING)

from epsm_data import build_archetype_from_spec
from epsm_data.infra.api.boverket_client import fetch_all_materials

JSON = Path("Data/opaque_material.json")

# Fetch Boverket once for all archetypes
print("Fetching Boverket API...")
api_resources = fetch_all_materials()
print(f"  → {len(api_resources)} resources loaded\n")

# ── Material shorthand ────────────────────────────────────────────
# Each tuple: (honeybee_id, boverket_id)
MAT = {
    "brick":        ("M01 100mm brick",                    "6000000082"),
    "concrete":     ("4 in. Normalweight Concrete Wall",   "6000000026"),
    "conc_floor":   ("100mm Normalweight concrete floor",  "6000000026"),
    "conc_roof":    ("6 in. Heavyweight Concrete Roof",    "6000000026"),
    "conc_bsmt":    ("8 in. Concrete Block Basement Wall", "6000000026"),
    "lw_concrete":  ("M11 100mm lightweight concrete",     "6000000085"),
    "mw_old":       ("Mineral Wool Old (created)",         "6000000123"),  # k=0.042
    "mw_new":       ("Mineral Wool New (created)",         "6000000123"),  # k=0.036
    "gypsum":       ("G01 13mm gypsum board",              "6000000020"),
    "plaster":      ("25mm Stucco",                        "6000000020"),
    "wood":         ("G05 25mm wood",                      "6000000007"),
    "plywood":      ("5/8 in. Plywood",                    "6000000023"),
    "eps":          ("I02 50mm insulation board",           "6000000131"),
    "roof_felt":    ("Built-up Roofing",                   "6000000132"),
}

def L(mat_key, thickness):
    """Create a layer spec from our material shorthand."""
    hb, bov = MAT[mat_key]
    return {"honeybee_id": hb, "boverket_id": bov, "thickness": thickness}

def composite(mat_keys, thickness, fractions):
    """Create a composite layer spec (e.g. timber stud + insulation)."""
    return {
        "honeybee_id": [MAT[k][0] for k in mat_keys],
        "boverket_id": [MAT[k][1] for k in mat_keys],
        "thickness": thickness,
        "area_fraction": fractions,
    }

# ══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════

def make_standard_roof(insul_mm, mw_key="mw_old", has_concrete_deck=True):
    """Flat/attic floor roof: optional concrete deck + insulation + felt."""
    layers = []
    if has_concrete_deck:
        layers.append(L("conc_roof", 0.150))
    layers.append(L(mw_key, insul_mm / 1000))
    layers.append(L("roof_felt", 0.006))
    return {"components": [{"shearing_layer": "Skin", "layers": layers}]}

def make_standard_floor(concrete_mm, insul_mm=0, insul_type="eps"):
    """Slab on grade: concrete + optional insulation underneath."""
    layers = []
    if insul_mm > 0:
        layers.append(L(insul_type, insul_mm / 1000))
    layers.append(L("conc_floor", concrete_mm / 1000))
    return {"components": [{"shearing_layer": "Structure", "layers": layers}]}

def make_basement_wall(concrete_mm, insul_mm=0, mw_key="mw_old"):
    """Basement wall: concrete + optional insulation."""
    layers = []
    layers.append(L("conc_bsmt", concrete_mm / 1000))
    if insul_mm > 0:
        layers.append(L(mw_key, insul_mm / 1000))
    return {"components": [{"shearing_layer": "Structure", "layers": layers}]}

def make_intermediate_floor(concrete_mm=200):
    """Intermediate floor: plain concrete slab."""
    return {"components": [{"shearing_layer": "Structure", "layers": [
        L("conc_floor", concrete_mm / 1000),
    ]}]}

def make_top_floor(concrete_mm=150, insul_mm=0, mw_key="mw_old"):
    """Top floor / attic floor: concrete + optional insulation."""
    layers = []
    layers.append(L("conc_floor", concrete_mm / 1000))
    if insul_mm > 0:
        layers.append(L(mw_key, insul_mm / 1000))
    return {"components": [{"shearing_layer": "Structure", "layers": layers}]}


# ══════════════════════════════════════════════════════════════════
# ARCHETYPE DEFINITIONS
# ══════════════════════════════════════════════════════════════════
# Insulation thicknesses are back-calculated from BETSI median U-values
# using actual honeybee conductivities:
#   mw_old  k=0.042 W/mK  (pre-1975 mineral wool)
#   mw_new  k=0.036 W/mK  (post-1975 mineral wool)
#   eps     k=0.030 W/mK
#
# Surface resistances: Rsi=0.13, Rse=0.04 (exterior), Rse=0.13 (interior)
# ══════════════════════════════════════════════════════════════════

ARCHETYPES = {}

# ── 1. Masonry Slab Block (pre-1960, n=38) ────────────────────
# Target: wall=0.46, roof=0.21, floor=0.27, win=2.50, bwall=0.85
# Brick masonry 1.5-sten (380mm) + added interior MW insulation
# Wall calc: Rsurf=0.17, plaster=0.028, brick=0.427, mw_old=t/0.042, plaster=0.021
#   1/0.46 = 2.174 → R_insul=1.53 → t=64mm
ARCHETYPES["BETSI_MASONRY_SLAB"] = {
    "archetype_id": "BETSI_MASONRY_SLAB",
    "display_name": "Masonry slab block (pre-1960)",
    "construction_year": 1945,
    "building_typology": "multi_family",
    "elements": {
        "EXT_WALL": {"components": [{"shearing_layer": "Skin", "layers": [
            L("plaster", 0.020),     # exterior render
            L("brick", 0.380),       # 1.5-sten masonry
            L("mw_old", 0.064),      # added MW insulation → U≈0.46
            L("plaster", 0.015),     # interior plaster
        ]}]},
        "ROOF": make_standard_roof(insul_mm=190, mw_key="mw_old"),  # → U≈0.21
        "TOP_FLOOR": make_top_floor(concrete_mm=150, insul_mm=190, mw_key="mw_old"),
        "INTERMEDIATE_FLOOR": make_intermediate_floor(200),
        "GROUND_FLOOR": make_standard_floor(concrete_mm=150, insul_mm=105),  # → U≈0.27
        "BASEMENT_FLOOR": make_standard_floor(concrete_mm=150, insul_mm=30),
        "BASEMENT_WALL": make_basement_wall(concrete_mm=250, insul_mm=35, mw_key="mw_old"),
        "WINDOW": {"u_value": 2.50, "shgc": 0.76},  # 2-pane clear, wood frame
    },
}

# ── 2. Masonry Tower Slab (pre-1940, n=12) ───────────────────
# Target: wall=0.73, roof=0.63, floor=0.38, win=2.50
# Thick masonry (380mm) with minimal added insulation
# Wall calc: R_other=0.646, 1/0.73=1.370 → R_insul=0.724 → t=30mm
ARCHETYPES["BETSI_MASONRY_TOWER"] = {
    "archetype_id": "BETSI_MASONRY_TOWER",
    "display_name": "Masonry tower slab (pre-1940)",
    "construction_year": 1935,
    "building_typology": "multi_family",
    "elements": {
        "EXT_WALL": {"components": [{"shearing_layer": "Skin", "layers": [
            L("plaster", 0.020),
            L("brick", 0.380),       # 1.5-sten masonry
            L("mw_old", 0.030),      # minimal added insulation → U≈0.73
            L("plaster", 0.015),
        ]}]},
        "ROOF": make_standard_roof(insul_mm=55, mw_key="mw_old"),   # → U≈0.63
        "TOP_FLOOR": make_top_floor(concrete_mm=150, insul_mm=55, mw_key="mw_old"),
        "INTERMEDIATE_FLOOR": make_intermediate_floor(200),
        "GROUND_FLOOR": make_standard_floor(concrete_mm=150, insul_mm=72),  # → U≈0.38
        "BASEMENT_FLOOR": make_standard_floor(concrete_mm=120, insul_mm=20),
        "BASEMENT_WALL": make_basement_wall(concrete_mm=250, insul_mm=35, mw_key="mw_old"),
        "WINDOW": {"u_value": 2.50, "shgc": 0.76},
    },
}

# ── 3. Concrete Slab Block (1960-75, miljonprogram, n=98) ─────
# Target: wall=0.25, roof=0.15, floor=0.27, win=2.00, bwall=0.42
# Concrete wall + external mineral wool + render
# Wall calc: R_other=0.337, 1/0.25=4.000 → R_insul=3.663 → t=154mm
ARCHETYPES["BETSI_CONC_SLAB"] = {
    "archetype_id": "BETSI_CONC_SLAB",
    "display_name": "Concrete slab block (1960-75)",
    "construction_year": 1968,
    "building_typology": "multi_family",
    "elements": {
        "EXT_WALL": {"components": [{"shearing_layer": "Skin", "layers": [
            L("plaster", 0.015),     # exterior render
            L("mw_old", 0.155),      # 155mm mineral wool → U≈0.25
            L("concrete", 0.150),    # concrete bearing wall
            L("gypsum", 0.013),      # interior gypsum
        ]}]},
        "ROOF": make_standard_roof(insul_mm=270, mw_key="mw_old"),  # → U≈0.15
        "TOP_FLOOR": make_top_floor(concrete_mm=150, insul_mm=270, mw_key="mw_old"),
        "INTERMEDIATE_FLOOR": make_intermediate_floor(200),
        "GROUND_FLOOR": make_standard_floor(concrete_mm=150, insul_mm=105),  # → U≈0.27
        "BASEMENT_FLOOR": make_standard_floor(concrete_mm=150, insul_mm=50),
        "BASEMENT_WALL": make_basement_wall(concrete_mm=200, insul_mm=85, mw_key="mw_old"),
        "WINDOW": {"u_value": 2.00, "shgc": 0.70},  # 2-pane, improved
    },
}

# ── 4. Concrete Tower Slab (1960-75, n=61) ────────────────────
# Target: wall=0.20, roof=0.14, floor=0.22, win=1.90, bwall=0.42
# Wall calc: R_other=0.337, 1/0.20=5.000 → R_insul=4.663 → t=196mm
ARCHETYPES["BETSI_CONC_TOWER"] = {
    "archetype_id": "BETSI_CONC_TOWER",
    "display_name": "Concrete tower slab (1960-75)",
    "construction_year": 1970,
    "building_typology": "multi_family",
    "elements": {
        "EXT_WALL": {"components": [{"shearing_layer": "Skin", "layers": [
            L("plaster", 0.015),
            L("mw_old", 0.195),      # 195mm MW → U≈0.20
            L("concrete", 0.150),
            L("gypsum", 0.013),
        ]}]},
        "ROOF": make_standard_roof(insul_mm=290, mw_key="mw_old"),  # → U≈0.14
        "TOP_FLOOR": make_top_floor(concrete_mm=150, insul_mm=290, mw_key="mw_old"),
        "INTERMEDIATE_FLOOR": make_intermediate_floor(200),
        "GROUND_FLOOR": make_standard_floor(concrete_mm=150, insul_mm=130),  # → U≈0.22
        "BASEMENT_FLOOR": make_standard_floor(concrete_mm=150, insul_mm=50),
        "BASEMENT_WALL": make_basement_wall(concrete_mm=200, insul_mm=85, mw_key="mw_old"),
        "WINDOW": {"u_value": 1.90, "shgc": 0.70},
    },
}

# ── 5. Concrete Point Block (1960-75, n=35) ───────────────────
# Target: wall=0.19, roof=0.15, floor=0.36, win=1.90, bwall=0.42
# Wall calc: R_other=0.337, 1/0.19=5.263 → R_insul=4.926 → t=207mm
ARCHETYPES["BETSI_CONC_POINT"] = {
    "archetype_id": "BETSI_CONC_POINT",
    "display_name": "Concrete point block (1960-75)",
    "construction_year": 1970,
    "building_typology": "multi_family",
    "elements": {
        "EXT_WALL": {"components": [{"shearing_layer": "Skin", "layers": [
            L("plaster", 0.015),
            L("mw_old", 0.205),      # 205mm MW → U≈0.19
            L("concrete", 0.150),
            L("gypsum", 0.013),
        ]}]},
        "ROOF": make_standard_roof(insul_mm=270, mw_key="mw_old"),  # → U≈0.15
        "TOP_FLOOR": make_top_floor(concrete_mm=150, insul_mm=270, mw_key="mw_old"),
        "INTERMEDIATE_FLOOR": make_intermediate_floor(200),
        "GROUND_FLOOR": make_standard_floor(concrete_mm=150, insul_mm=76),  # → U≈0.36
        "BASEMENT_FLOOR": make_standard_floor(concrete_mm=100, insul_mm=30),
        "BASEMENT_WALL": make_basement_wall(concrete_mm=200, insul_mm=85, mw_key="mw_old"),
        "WINDOW": {"u_value": 1.90, "shgc": 0.70},
    },
}

# ── 6. Concrete Gallery Access (1960-75, n=30) ────────────────
# Target: wall=0.23, roof=0.12, floor=0.23, win=1.90, bwall=0.42
# Wall calc: R_other=0.337, 1/0.23=4.348 → R_insul=4.011 → t=168mm
ARCHETYPES["BETSI_CONC_GALLERY"] = {
    "archetype_id": "BETSI_CONC_GALLERY",
    "display_name": "Concrete gallery access (1960-75)",
    "construction_year": 1970,
    "building_typology": "multi_family",
    "elements": {
        "EXT_WALL": {"components": [{"shearing_layer": "Skin", "layers": [
            L("plaster", 0.015),
            L("mw_old", 0.170),      # 170mm MW → U≈0.23
            L("concrete", 0.150),
            L("gypsum", 0.013),
        ]}]},
        "ROOF": make_standard_roof(insul_mm=340, mw_key="mw_old"),  # → U≈0.12
        "TOP_FLOOR": make_top_floor(concrete_mm=150, insul_mm=340, mw_key="mw_old"),
        "INTERMEDIATE_FLOOR": make_intermediate_floor(200),
        "GROUND_FLOOR": make_standard_floor(concrete_mm=150, insul_mm=125),  # → U≈0.23
        "BASEMENT_FLOOR": make_standard_floor(concrete_mm=150, insul_mm=50),
        "BASEMENT_WALL": make_basement_wall(concrete_mm=200, insul_mm=85, mw_key="mw_old"),
        "WINDOW": {"u_value": 1.90, "shgc": 0.70},
    },
}

# ── 7. Concrete Prefab Slab (1965-75, n=43) ───────────────────
# Target: wall=0.25, roof=0.14, floor=0.25, win=2.00, bwall=0.42
# Sandwich panels: conc(70)+MW+conc(150)+gypsum
# Wall calc: R_other=0.347, 1/0.25=4.000 → R_insul=3.653 → t=153mm
ARCHETYPES["BETSI_CONC_PREFAB"] = {
    "archetype_id": "BETSI_CONC_PREFAB",
    "display_name": "Concrete prefab slab (1965-75)",
    "construction_year": 1970,
    "building_typology": "multi_family",
    "elements": {
        "EXT_WALL": {"components": [{"shearing_layer": "Skin", "layers": [
            L("concrete", 0.070),    # outer concrete leaf
            L("mw_old", 0.155),      # 155mm insulation core → U≈0.25
            L("concrete", 0.150),    # inner concrete leaf
            L("gypsum", 0.013),
        ]}]},
        "ROOF": make_standard_roof(insul_mm=290, mw_key="mw_old"),  # → U≈0.14
        "TOP_FLOOR": make_top_floor(concrete_mm=150, insul_mm=290, mw_key="mw_old"),
        "INTERMEDIATE_FLOOR": make_intermediate_floor(200),
        "GROUND_FLOOR": make_standard_floor(concrete_mm=150, insul_mm=115),  # → U≈0.25
        "BASEMENT_FLOOR": make_standard_floor(concrete_mm=150, insul_mm=50),
        "BASEMENT_WALL": make_basement_wall(concrete_mm=200, insul_mm=85, mw_key="mw_old"),
        "WINDOW": {"u_value": 2.00, "shgc": 0.70},
    },
}

# ── 8. All-Concrete Slab Block (1960-80, n=46) ────────────────
# Target: wall=0.31, roof=0.14, floor=0.23, win=1.90, bwall=0.64
# Sandwich concrete panels: conc(70)+MW+conc(150), no gypsum finish
# Wall calc: R_other=0.265, 1/0.31=3.226 → R_insul=2.961 → t=124mm
ARCHETYPES["BETSI_ALLCONC_SLAB"] = {
    "archetype_id": "BETSI_ALLCONC_SLAB",
    "display_name": "All-concrete slab block (1960-80)",
    "construction_year": 1970,
    "building_typology": "multi_family",
    "elements": {
        "EXT_WALL": {"components": [{"shearing_layer": "Skin", "layers": [
            L("concrete", 0.070),    # outer leaf
            L("mw_old", 0.125),      # 125mm insulation → U≈0.31
            L("concrete", 0.150),    # inner leaf (load-bearing)
        ]}]},
        "ROOF": make_standard_roof(insul_mm=290, mw_key="mw_old"),  # → U≈0.14
        "TOP_FLOOR": make_top_floor(concrete_mm=150, insul_mm=290, mw_key="mw_old"),
        "INTERMEDIATE_FLOOR": make_intermediate_floor(200),
        "GROUND_FLOOR": make_standard_floor(concrete_mm=150, insul_mm=125),  # → U≈0.23
        "BASEMENT_FLOOR": make_standard_floor(concrete_mm=150, insul_mm=50),
        "BASEMENT_WALL": make_basement_wall(concrete_mm=200, insul_mm=50, mw_key="mw_old"),
        "WINDOW": {"u_value": 1.90, "shgc": 0.70},
    },
}

# ── 9. All-Concrete Tower Slab (1960-80, n=32) ────────────────
# Target: wall=0.32, roof=0.14, floor=0.25, win=1.90, bwall=0.64
# Wall calc: R_other=0.265, 1/0.32=3.125 → R_insul=2.860 → t=120mm
ARCHETYPES["BETSI_ALLCONC_TOWER"] = {
    "archetype_id": "BETSI_ALLCONC_TOWER",
    "display_name": "All-concrete tower slab (1960-80)",
    "construction_year": 1970,
    "building_typology": "multi_family",
    "elements": {
        "EXT_WALL": {"components": [{"shearing_layer": "Skin", "layers": [
            L("concrete", 0.070),
            L("mw_old", 0.120),      # 120mm insulation → U≈0.32
            L("concrete", 0.150),
        ]}]},
        "ROOF": make_standard_roof(insul_mm=290, mw_key="mw_old"),  # → U≈0.14
        "TOP_FLOOR": make_top_floor(concrete_mm=150, insul_mm=290, mw_key="mw_old"),
        "INTERMEDIATE_FLOOR": make_intermediate_floor(200),
        "GROUND_FLOOR": make_standard_floor(concrete_mm=150, insul_mm=115),  # → U≈0.25
        "BASEMENT_FLOOR": make_standard_floor(concrete_mm=150, insul_mm=30),
        "BASEMENT_WALL": make_basement_wall(concrete_mm=200, insul_mm=50, mw_key="mw_old"),
        "WINDOW": {"u_value": 1.90, "shgc": 0.70},
    },
}

# ── 10. All-Concrete Point Block (1960-80, n=16) ──────────────
# Target: wall=0.26, roof=0.15, floor=0.18, win=1.90, bwall=0.64
# Wall calc: R_other=0.265, 1/0.26=3.846 → R_insul=3.581 → t=150mm
ARCHETYPES["BETSI_ALLCONC_POINT"] = {
    "archetype_id": "BETSI_ALLCONC_POINT",
    "display_name": "All-concrete point block (1960-80)",
    "construction_year": 1972,
    "building_typology": "multi_family",
    "elements": {
        "EXT_WALL": {"components": [{"shearing_layer": "Skin", "layers": [
            L("concrete", 0.070),
            L("mw_old", 0.150),      # 150mm insulation → U≈0.26
            L("concrete", 0.150),
        ]}]},
        "ROOF": make_standard_roof(insul_mm=270, mw_key="mw_old"),  # → U≈0.15
        "TOP_FLOOR": make_top_floor(concrete_mm=150, insul_mm=270, mw_key="mw_old"),
        "INTERMEDIATE_FLOOR": make_intermediate_floor(200),
        "GROUND_FLOOR": make_standard_floor(concrete_mm=150, insul_mm=160),  # → U≈0.18
        "BASEMENT_FLOOR": make_standard_floor(concrete_mm=150, insul_mm=80),
        "BASEMENT_WALL": make_basement_wall(concrete_mm=200, insul_mm=50, mw_key="mw_old"),
        "WINDOW": {"u_value": 1.90, "shgc": 0.70},
    },
}

# ── 11. All-Concrete Prefab (1965-80, n=25) ───────────────────
# Target: wall=0.28, roof=0.12, floor=0.18, win=2.00, bwall=0.64
# Wall calc: R_other=0.265, 1/0.28=3.571 → R_insul=3.306 → t=139mm
ARCHETYPES["BETSI_ALLCONC_PREFAB"] = {
    "archetype_id": "BETSI_ALLCONC_PREFAB",
    "display_name": "All-concrete prefab (1965-80)",
    "construction_year": 1972,
    "building_typology": "multi_family",
    "elements": {
        "EXT_WALL": {"components": [{"shearing_layer": "Skin", "layers": [
            L("concrete", 0.070),    # prefab outer leaf
            L("mw_old", 0.140),      # 140mm core → U≈0.28
            L("concrete", 0.150),
        ]}]},
        "ROOF": make_standard_roof(insul_mm=340, mw_key="mw_old"),  # → U≈0.12
        "TOP_FLOOR": make_top_floor(concrete_mm=150, insul_mm=340, mw_key="mw_old"),
        "INTERMEDIATE_FLOOR": make_intermediate_floor(200),
        "GROUND_FLOOR": make_standard_floor(concrete_mm=150, insul_mm=160),  # → U≈0.18
        "BASEMENT_FLOOR": make_standard_floor(concrete_mm=150, insul_mm=80),
        "BASEMENT_WALL": make_basement_wall(concrete_mm=200, insul_mm=50, mw_key="mw_old"),
        "WINDOW": {"u_value": 2.00, "shgc": 0.70},
    },
}

# ── 12. Timber MF Villa (mixed era, n=21) ─────────────────────
# Target: wall=0.20, roof=0.15, floor=0.41, win=2.00, bwall=0.81
# Timber stud wall: wood cladding + plywood + 195mm stud+MW composite + extra MW + gypsum
# Composite k_eff = 0.15×0.1499 + 0.85×0.042 = 0.0582
# Wall calc: R_other=0.498, R_stud(195mm)=3.35, need extra 45mm MW → total R≈4.92 → U≈0.20
ARCHETYPES["BETSI_TIMBER_VILLA"] = {
    "archetype_id": "BETSI_TIMBER_VILLA",
    "display_name": "Timber multi-family villa (mixed era)",
    "construction_year": 1955,
    "building_typology": "multi_family",
    "elements": {
        "EXT_WALL": {"components": [{"shearing_layer": "Skin", "layers": [
            L("wood", 0.022),        # wood cladding
            L("plywood", 0.012),     # wind barrier
            # 195mm stud wall: 15% timber, 85% mineral wool
            composite(["wood", "mw_old"], 0.195, [0.15, 0.85]),
            L("mw_old", 0.045),      # extra interior insulation board
            L("gypsum", 0.013),
        ]}]},
        "ROOF": make_standard_roof(insul_mm=270, mw_key="mw_old", has_concrete_deck=False),  # → U≈0.15
        "TOP_FLOOR": {"components": [{"shearing_layer": "Structure", "layers": [
            L("wood", 0.022),         # ceiling boards
            L("mw_old", 0.270),       # matches roof insulation
        ]}]},
        "INTERMEDIATE_FLOOR": {"components": [{"shearing_layer": "Structure", "layers": [
            L("wood", 0.045),         # timber joist floor
            L("conc_floor", 0.050),   # screed topping
        ]}]},
        "GROUND_FLOOR": make_standard_floor(concrete_mm=100, insul_mm=65),  # → U≈0.41
        "BASEMENT_FLOOR": make_standard_floor(concrete_mm=100, insul_mm=20),
        "BASEMENT_WALL": make_basement_wall(concrete_mm=200, insul_mm=38, mw_key="mw_old"),
        "WINDOW": {"u_value": 2.00, "shgc": 0.76},  # older 2-pane
    },
}

# ── 13. Timber Terraced (1975+, n=12) ─────────────────────────
# Target: wall=0.20, roof=0.13, floor=0.20, win=2.00, bwall=0.81
# Uses mw_new (k=0.036) for post-1975 construction
# Composite k_eff = 0.15×0.1499 + 0.85×0.036 = 0.0531
# Wall calc: R_other=0.498, R_stud(195mm)=3.67, need extra 30mm MW → total R≈5.00 → U≈0.20
ARCHETYPES["BETSI_TIMBER_TERRACE"] = {
    "archetype_id": "BETSI_TIMBER_TERRACE",
    "display_name": "Timber terraced house (1975+)",
    "construction_year": 1975,
    "building_typology": "multi_family",
    "elements": {
        "EXT_WALL": {"components": [{"shearing_layer": "Skin", "layers": [
            L("wood", 0.022),
            L("plywood", 0.012),
            composite(["wood", "mw_new"], 0.195, [0.15, 0.85]),
            L("mw_new", 0.030),      # extra interior insulation
            L("gypsum", 0.013),
        ]}]},
        "ROOF": make_standard_roof(insul_mm=270, mw_key="mw_new", has_concrete_deck=False),  # → U≈0.13
        "TOP_FLOOR": {"components": [{"shearing_layer": "Structure", "layers": [
            L("wood", 0.022),
            L("mw_new", 0.270),
        ]}]},
        "INTERMEDIATE_FLOOR": {"components": [{"shearing_layer": "Structure", "layers": [
            L("wood", 0.045),
            L("conc_floor", 0.050),
        ]}]},
        "GROUND_FLOOR": make_standard_floor(concrete_mm=100, insul_mm=145),  # → U≈0.20
        "BASEMENT_FLOOR": make_standard_floor(concrete_mm=100, insul_mm=50),
        "BASEMENT_WALL": make_basement_wall(concrete_mm=200, insul_mm=33, mw_key="mw_new"),
        "WINDOW": {"u_value": 2.00, "shgc": 0.70},
    },
}


# ══════════════════════════════════════════════════════════════════
# BUILD & VALIDATE
# ══════════════════════════════════════════════════════════════════

# Target U-values from BETSI medians (per archetype)
TARGETS = {
    "BETSI_MASONRY_SLAB":    {"EXT_WALL": 0.46, "ROOF": 0.21, "GROUND_FLOOR": 0.27, "WINDOW": 2.50},
    "BETSI_MASONRY_TOWER":   {"EXT_WALL": 0.73, "ROOF": 0.63, "GROUND_FLOOR": 0.38, "WINDOW": 2.50},
    "BETSI_CONC_SLAB":       {"EXT_WALL": 0.25, "ROOF": 0.15, "GROUND_FLOOR": 0.27, "WINDOW": 2.00},
    "BETSI_CONC_TOWER":      {"EXT_WALL": 0.20, "ROOF": 0.14, "GROUND_FLOOR": 0.22, "WINDOW": 1.90},
    "BETSI_CONC_POINT":      {"EXT_WALL": 0.19, "ROOF": 0.15, "GROUND_FLOOR": 0.36, "WINDOW": 1.90},
    "BETSI_CONC_GALLERY":    {"EXT_WALL": 0.23, "ROOF": 0.12, "GROUND_FLOOR": 0.23, "WINDOW": 1.90},
    "BETSI_CONC_PREFAB":     {"EXT_WALL": 0.25, "ROOF": 0.14, "GROUND_FLOOR": 0.25, "WINDOW": 2.00},
    "BETSI_ALLCONC_SLAB":    {"EXT_WALL": 0.31, "ROOF": 0.14, "GROUND_FLOOR": 0.23, "WINDOW": 1.90},
    "BETSI_ALLCONC_TOWER":   {"EXT_WALL": 0.32, "ROOF": 0.14, "GROUND_FLOOR": 0.25, "WINDOW": 1.90},
    "BETSI_ALLCONC_POINT":   {"EXT_WALL": 0.26, "ROOF": 0.15, "GROUND_FLOOR": 0.18, "WINDOW": 1.90},
    "BETSI_ALLCONC_PREFAB":  {"EXT_WALL": 0.28, "ROOF": 0.12, "GROUND_FLOOR": 0.18, "WINDOW": 2.00},
    "BETSI_TIMBER_VILLA":    {"EXT_WALL": 0.20, "ROOF": 0.15, "GROUND_FLOOR": 0.41, "WINDOW": 2.00},
    "BETSI_TIMBER_TERRACE":  {"EXT_WALL": 0.20, "ROOF": 0.13, "GROUND_FLOOR": 0.20, "WINDOW": 2.00},
}

results = {}
print(f"{'Archetype':30s} {'Element':20s} {'Computed':>8s} {'Target':>8s} {'Diff%':>7s} {'Status':>6s}")
print("=" * 85)

for archetype_id, spec in ARCHETYPES.items():
    try:
        arch = build_archetype_from_spec(spec, JSON, api_resources=api_resources)
        results[archetype_id] = arch

        targets = TARGETS[archetype_id]
        for role, elem in arch.construction_set.elements.items():
            computed = elem.u_value
            target = targets.get(role.value)
            if target is not None:
                diff_pct = (computed - target) / target * 100
                status = "OK" if abs(diff_pct) < 25 else "CHECK"
                print(f"{archetype_id:30s} {role.value:20s} {computed:8.3f} {target:8.3f} {diff_pct:+6.1f}% {status:>6s}")
            else:
                print(f"{archetype_id:30s} {role.value:20s} {computed:8.3f} {'—':>8s}")
    except Exception as exc:
        print(f"{archetype_id:30s} ERROR: {exc}")

print(f"\nSuccessfully built: {len(results)} / {len(ARCHETYPES)} archetypes")
