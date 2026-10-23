"""Inspect accepted LoD2 constructions and report any missing fabric values."""

from epsm_data import Catalogue, archetype_from_dict, archetype_to_dict


def main():
    catalogue = Catalogue.load()
    print(catalogue.summary())
    for state in ("existing", "standard", "advanced"):
        archetype = catalogue.get("mf_se02", state=state)
        assert archetype_from_dict(archetype_to_dict(archetype)) == archetype
        print(archetype)
        print("Physical U-values:", archetype.envelope_u_values)
        print("Completeness:", catalogue.completeness("mf_se02", state=state))


if __name__ == "__main__":
    main()
