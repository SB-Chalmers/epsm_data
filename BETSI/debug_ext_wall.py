"""Debug: trace CMF_1960_1_EXT_WALL layer stack."""
from pathlib import Path
from epsm_data import setup_logging, run_build_baseline
import logging

setup_logging(level=logging.WARNING)
result = run_build_baseline(Path("Data/Material_Database.xlsx"), Path("Data/opaque_material.json"))

for arch in result.archetypes:
    if arch.archetype_id == "CMF_1960_1":
        for role, elem in arch.construction_set.elements.items():
            if role.is_ext_wall:
                print(f"Element: {elem.name}  U={elem.u_value:.4f}  R_total={elem.r_total:.4f}")
                try:
                    print(f"  RSI={elem.rsi:.3f}  RSE={elem.rse:.3f}")
                except Exception as e:
                    print(f"  RSI/RSE error: {e}")
                print(f"  # components: {len(elem.components)}")
                for comp in elem.components:
                    try:
                        print(f"  Component: {comp.name}  R={comp.r_sum:.4f}  t={comp.thickness:.4f}m")
                        print(f"    # layers: {len(comp.layers)}")
                        for layer, idx in comp.layers:
                            r = layer.r_value
                            print(f"    [{idx}] {layer.name}  t={layer.thickness:.4f}m  R={r:.4f}  composite={layer.is_composite}")
                            for lm in layer.materials:
                                print(f"        mat={lm.material.name}  k={lm.material.conductivity:.4f}  frac={lm.area_fraction:.3f}")
                    except Exception as e:
                        print(f"    ERROR in {comp.name}: {e}")
