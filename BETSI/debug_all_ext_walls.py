"""Review ext wall layer stacks for all archetypes with TABULA warnings."""
from pathlib import Path
from epsm_data import setup_logging, run_build_baseline
import logging

setup_logging(level=logging.WARNING)
result = run_build_baseline(Path("Data/Material_Database.xlsx"), Path("Data/opaque_material.json"))

for arch in result.archetypes:
    for role, elem in arch.construction_set.elements.items():
        if not role.is_ext_wall:
            continue
        print(f"\n{'='*70}")
        print(f"{elem.name}  U={elem.u_value:.4f}  R_total={1/elem.u_value:.4f}")
        print(f"{'='*70}")
        for comp in elem.components:
            print(f"  Component: {comp.name}  R={comp.r_sum:.4f}  t={comp.thickness:.4f}m")
            for layer, idx in comp.layers:
                r = layer.r_value
                t = sum(lm.thickness for lm in layer.materials)
                print(f"    [{idx}] {layer.name}  t={t:.4f}m  R={r:.4f}  composite={layer.is_composite}")
                for lm in layer.materials:
                    print(f"        {lm.material.name:<30} k={lm.material.conductivity:.4f}  frac={lm.area_fraction:.3f}  t={lm.thickness:.4f}")
