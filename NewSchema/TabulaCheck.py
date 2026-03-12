from Classes import Elements, TABULA_CMF

def analyse_tabula_failures(elements: list[Elements]) -> None:
    """
    For each element that fails the Tabula check, prints a full breakdown
    of what is driving the U-value and how far it is from the threshold.
    """
    failures = [el for el in elements if el.tabula_warning]

    if not failures:
        print("All elements pass Tabula.")
        return

    print(f"\n{'='*70}")
    print(f"TABULA ANALYSIS — {len(failures)} failing element(s)")
    print(f"{'='*70}")

    for el in failures:
        tabula_u = el.tabula_u_value
        target_u = tabula_u * 1.10
        matched_archetype = el.match_tabula(TABULA_CMF)

        r_components = sum(c.r_sum for c in el.components)
        r_total = 0.13 + r_components + 0.04

        print(f"\n  Element  : {el.name}")
        print(f"  Type     : {el.application.value}  |  Archetype: {matched_archetype}")
        print(f"  U-value  : {el.u_value:.4f} W/m²K  (threshold: {target_u:.4f}, tabula: {tabula_u:.4f})")
        print(f"  Gap      : needs R_total ≥ {1/target_u:.4f} m²K/W, currently {r_total:.4f}")
        print(f"  R needed to pass: +{(1/target_u) - r_total:.4f} m²K/W")
        print(f"\n  {'Component':<35} {'R_sum':>8}  {'% of R_comp':>12}")
        print(f"  {'-'*58}")

        for comp in el.components:
            pct = (comp.r_sum / r_components * 100) if r_components > 0 else 0
            print(f"  {comp.name:<35} {comp.r_sum:>8.4f}  {pct:>11.1f}%")

            for layer, idx in comp.layers:
                layer_pct = (layer.r_value / r_components * 100) if r_components > 0 else 0
                print(f"    [{idx}] {layer.layer_code:<30} d={layer.thickness*1000:.1f}mm  R={layer.r_value:.4f}  ({layer_pct:.1f}%)")

                for mat, frac, t in layer.materials:
                    print(f"         {mat.name:<28} λ={mat.conductivity:.3f}  frac={frac:.2f}  d={t*1000:.1f}mm")