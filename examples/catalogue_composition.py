"""Inspect physical composition separately from catalogue target acceptance."""

from epsm_data import Catalogue, archetype_from_dict, archetype_to_dict


def main():
    catalogue = Catalogue.load()
    for state in ("existing", "standard", "advanced"):
        archetype = catalogue.get("mf_se02", state=state)
        assert archetype.total_elements == 7
        assert archetype_from_dict(archetype_to_dict(archetype)) == archetype
        print(archetype)
        print("Physical U-values:", archetype.envelope_u_values)
        print("Structured caveats:", len(catalogue.detailed.review("mf_se02", state)["caveats"]))


if __name__ == "__main__":
    main()
