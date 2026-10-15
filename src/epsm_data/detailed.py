"""Shared material, assembly and archetype registries, with review annotations.

Mapping, assembly, archetype and two source JSON files are authoritative. Resolved stacks and reports are generated;
historical evidence snapshots are never consulted by this loader.
"""

# Release contract: v1.4 preserves v1.3 roles; see evidence/lod2_v1_4/window-diagnostic.json.
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
from copy import deepcopy
from dataclasses import dataclass, replace
from importlib.resources import files
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from epsm_data._logging import operation as logged_operation

from .domain import BuildingElement, EmbodiedCarbon, OpaqueMaterial, Roughness, ShearingLayer
from .parametric import ArchetypeKey, EffectiveProperty, _load_parametric_catalogue

REGISTRIES = ("materials", "assemblies", "archetypes", "honeybee", "boverket")
CAVEAT_STATUSES = {"open", "accepted_assumption", "resolved"}
CAVEAT_SEVERITIES = {"info", "warning", "blocking"}
logger = logging.getLogger(__name__)


def _opaque_material(properties):
    """Construct one reusable material with the established physical identity."""
    fields = deepcopy(properties)
    encoded = json.dumps(fields, sort_keys=True, ensure_ascii=False, allow_nan=False)
    revision = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    fields["uuid"] = uuid5(NAMESPACE_URL, f"epsm_data:material:{revision}")
    fields["roughness"] = Roughness(fields["roughness"])
    carbon = fields["embodied_carbon"]
    fields["embodied_carbon"] = EmbodiedCarbon(**carbon) if carbon is not None else None
    return OpaqueMaterial(**fields)


def _number(value, label, *, positive=True):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or (value <= 0 if positive else value < 0)):
        raise ValueError(f"Invalid {label}")
    return value


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _nonfinite(value):
    raise ValueError(f"Nonfinite JSON value: {value}")


def _annotations(record, owner, sources):
    notes, caveats = record.get("notes"), record.get("caveats")
    if not isinstance(notes, list) or any(not isinstance(n, str) or not n.strip() for n in notes):
        raise ValueError(f"{owner}: notes must be a list of nonempty strings")
    if not isinstance(caveats, list):
        raise ValueError(f"{owner}: caveats must be a list")
    seen = set()
    for item in caveats:
        if not isinstance(item, dict):
            raise ValueError(f"{owner}: caveat must be an object")
        cid = item.get("id")
        if not isinstance(cid, str) or not cid.strip() or cid in seen:
            raise ValueError(f"{owner}: duplicate or missing caveat ID")
        seen.add(cid)
        if item.get("status") not in CAVEAT_STATUSES or item.get("severity") not in CAVEAT_SEVERITIES:
            raise ValueError(f"{owner}: invalid caveat status/severity")
        if item.get("scope", "catalogue") not in {"catalogue", "simulation", "carbon_assessment"}:
            raise ValueError(f"{owner}: invalid caveat scope")
        if not isinstance(item.get("note"), str) or not item["note"].strip():
            raise ValueError(f"{owner}: caveat requires an explanation")
        resolution = item.get("resolution")
        if resolution is not None and (not isinstance(resolution, str) or not resolution.strip()):
            raise ValueError(f"{owner}: resolution must be text or null")
        if item["status"] == "resolved" and resolution is None:
            raise ValueError(f"{owner}: resolved caveat requires resolution text")
        if item.get("source") is not None and item["source"] not in sources:
            raise ValueError(f"{owner}: dangling caveat source")


def _source(record, owner, sources):
    if record.get("source") not in sources or not (record.get("locator") or record.get("notes")):
        raise ValueError(f"{owner}: reference requires source and locator or explanatory notes")


@dataclass(frozen=True, repr=False)
class DetailedCatalogue:
    """Validated authoring data; dictionary access/export returns defensive copies."""

    _data: dict

    def __repr__(self):
        counts = {key: len(self._data[key][key])
                  for key in ("archetypes", "assemblies", "materials")}
        return (f"DetailedCatalogue(archetypes={counts['archetypes']}, "
                f"assemblies={counts['assemblies']}, materials={counts['materials']})")

    __str__ = __repr__

    def to_dict(self):
        data = deepcopy(self._data)
        for archetype in data["archetypes"]["archetypes"].values():
            if archetype["era"] == "SE.07":
                archetype["configuration"] = archetype.pop("states")[None]
        return data

    @property
    def materials(self):
        return deepcopy(self._data["materials"]["materials"])

    @property
    def assemblies(self):
        return deepcopy(self._data["assemblies"]["assemblies"])

    @property
    def archetypes(self):
        return deepcopy(self._data["archetypes"]["archetypes"])

    @property
    def sources(self):
        return deepcopy(self._data["materials"]["sources"])

    @property
    def honeybee_materials(self):
        return deepcopy(self._data["honeybee"]["materials"])

    @property
    def boverket_resources(self):
        return {str(r["ResourceId"]): deepcopy(r) for r in self._data["boverket"]["Resources"]}

    def resolve_material(self, mid):
        """Join source references in memory; this is not another authoring database."""
        return _resolve_material(self._data, mid)

    def _records(self, archetype_id, state):
        archetype = self._data["archetypes"]["archetypes"][archetype_id]
        variant = archetype["states"][state]
        states = [state] if "base_state" not in variant else [variant["base_state"], state]
        aids = set()
        for name in states:
            s = archetype["states"][name]
            aids.update(s.get("assemblies", {}).values())
            aids.update(op["assembly_id"] for op in s.get("operations", []))
        mids = set()
        records = [("archetype", archetype_id, archetype)]
        records += [("state", f"{archetype_id}:{s}", archetype["states"][s]) for s in states]
        for aid in sorted(aids):
            assembly = self._data["assemblies"]["assemblies"][aid]
            records.append(("assembly", aid, assembly))
            if assembly["role"] == "WINDOW":
                mids.add(assembly["material_id"])
            for ci, component in enumerate(assembly.get("components", [])):
                records.append(("component", f"{aid}:C{ci}", component))
                for li, layer in enumerate(component["layers"]):
                    records.append(("layer", f"{aid}:C{ci}:L{li}", layer))
                    mid = layer["material_id"]
                    mids.update([mid] if isinstance(mid, str) else mid)
        records += [("material", mid, self._data["materials"]["materials"][mid]) for mid in sorted(mids)]
        for hid in sorted({self._data["materials"]["materials"][mid]["honeybee_id"] for mid in mids}):
            records.append(("honeybee", hid, self._data["honeybee"]["materials"][hid]["user_data"]))
        for oi, operation in enumerate(variant.get("operations", [])):
            records.append(("operation", f"{archetype_id}:{state}:R{oi}", operation))
        records += [("registry", name, self._data[name]) for name in REGISTRIES]
        return records

    def active_material_ids(self, archetype_id="mf_se02", state="existing"):
        """Products actually used after removals/replacements, excluding old history."""
        a = self._data["archetypes"]["archetypes"][archetype_id]
        base = a["states"][state] if "assemblies" in a["states"][state] else a["states"]["existing"]
        stacks = {role: deepcopy(self._data["assemblies"]["assemblies"][aid]) for role, aid in base["assemblies"].items()}
        for op in a["states"][state].get("operations", []):
            assembly = self._data["assemblies"]["assemblies"][op["assembly_id"]]
            if op["action"] == "replace_window":
                stacks[op["role"]] = assembly
            else:
                old = stacks[op["role"]]["components"]
                if op["action"] == "replace_exterior":
                    old = old[op["remove_components"]:]
                added = assembly["components"]
                stacks[op["role"]]["components"] = (added + old if op["position"] == "outside"
                                                    else old[:-1] + added + old[-1:])
        mids = set()
        for assembly in stacks.values():
            if assembly["role"] == "WINDOW":
                mids.add(assembly["material_id"])
            for component in assembly.get("components", []):
                for layer in component["layers"]:
                    mid = layer["material_id"]
                    mids.update([mid] if isinstance(mid, str) else mid)
        return tuple(sorted(mids))

    def material_references(self, archetype_id="mf_se02", state="existing"):
        return {mid: {"registry_id": mid, **{f: self.resolve_material(mid)[f] for f in
                    ("json_id", "honeybee_id", "boverket_id", "mapping_status", "kind",
                     "honeybee_revision", "boverket_revision")}}
                for mid in self.active_material_ids(archetype_id, state)}

    def boundary_details(self, archetype_id="mf_se02", state="existing"):
        a = self._data["archetypes"]["archetypes"][archetype_id]
        refs = dict((a["states"][state] if "assemblies" in a["states"][state]
                     else a["states"]["existing"])["assemblies"])
        refs.update({op["role"]: op["assembly_id"] for op in a["states"][state].get("operations", [])})
        return {role: deepcopy(self._data["assemblies"]["assemblies"][aid].get("boundary_details", {})) for role, aid in refs.items()}

    def annotations(self, archetype_id="mf_se02", state="existing"):
        """Notes/caveats with explicit owner IDs, including resolved history."""
        return [{"owner_type": kind, "owner_id": rid,
                 "notes": deepcopy(record["notes"]), "caveats": deepcopy(record["caveats"])}
                for kind, rid, record in self._records(archetype_id, state)]

    def caveats(self, archetype_id="mf_se02", state="existing", *, status=None, severity=None):
        if status is not None and status not in CAVEAT_STATUSES:
            raise ValueError("Invalid caveat status filter")
        if severity is not None and severity not in CAVEAT_SEVERITIES:
            raise ValueError("Invalid caveat severity filter")
        return [{"owner_type": item["owner_type"], "owner_id": item["owner_id"], **caveat}
                for item in self.annotations(archetype_id, state) for caveat in item["caveats"]
                if (status is None or caveat["status"] == status)
                and (severity is None or caveat["severity"] == severity)]

    def retained_floor_unmapped_materials(self, archetype_id, state):
        """Verify an explicit baseline-only carbon gap; never exempt new products."""
        states = self._data["archetypes"]["archetypes"][archetype_id]["states"]
        declared = states[state].get("v1_review", {}).get("retained_floor_unmapped_materials", [])
        if not declared:
            return []
        if set(states) not in ({"existing", "standard", "advanced"}, {None}):
            raise ValueError("Retained floor mapping review requires all three states")
        reference = None
        for variant in states.values():
            if variant.get("operations"):
                raise ValueError("Retained floor mapping review requires explicit full recipes")
            if variant.get("v1_review", {}).get("retained_floor_unmapped_materials") != declared:
                raise ValueError("Retained floor mapping declarations differ between states")
            if any(i["material_id"] in declared for i in variant.get("v1_review", {}).get("incoming_materials", [])):
                raise ValueError("Incoming materials cannot use a retained floor mapping exemption")
            floor_ids = set()
            for role, ref in variant["assemblies"].items():
                assembly = self._data["assemblies"]["assemblies"][ref]
                mids = {mid for c in assembly.get("components", []) for layer in c["layers"]
                        for mid in (layer["material_id"] if isinstance(layer["material_id"], list) else [layer["material_id"]])}
                if role != "INTERMEDIATE_FLOOR" and mids.intersection(declared):
                    raise ValueError("Retained floor material used outside the retained floor")
                if role == "INTERMEDIATE_FLOOR":
                    floor_ids = mids
                    components = assembly["components"]
                    if reference is not None and components != reference:
                        raise ValueError("Retained floor changed between renovation states")
                    reference = components
            if not set(declared) <= floor_ids:
                raise ValueError("Declared retained material absent from floor")
        if any(self.materials[mid]["mapping_status"] != "pending" for mid in declared):
            raise ValueError("Retained floor exception only applies to unmapped baseline materials")
        return sorted(declared)

    @logged_operation("catalogue.validate", level=10)
    def review(self, archetype_id, state):
        annotations = self.annotations(archetype_id, state)
        caveats = self.caveats(archetype_id, state)
        fitting = self._data["archetypes"]["archetypes"][archetype_id]["states"][state].get("lod2_fitting")
        return {
            **({"lod2_fitting": deepcopy(fitting)} if fitting is not None else {}),
            **({"v1_review": deepcopy(self._data["archetypes"]["archetypes"][archetype_id]["states"][state]["v1_review"])}
               if "v1_review" in self._data["archetypes"]["archetypes"][archetype_id]["states"][state] else {}),
            "notes": [*self._data["archetypes"]["archetypes"][archetype_id]["notes"],
                      *self._data["archetypes"]["archetypes"][archetype_id]["states"][state]["notes"]],
            "caveats": caveats, "record_annotations": annotations,
            "open_caveats": [c for c in caveats if c["status"] == "open"],
            "blocking_caveats": [c for c in caveats if c["status"] == "open" and c["severity"] == "blocking"],
            "material_references": self.material_references(archetype_id, state),
            "boundary_details": self.boundary_details(archetype_id, state),
            **({"retained_baseline_unmapped_materials": retained} if (retained := self.retained_floor_unmapped_materials(archetype_id, state)) else {}),
        }

    def _material(self, mid):
        record = self.resolve_material(mid)
        record["registry_id"] = mid
        record["note"] = " ".join(record["notes"]) or record.get("locator", "")
        record.setdefault("locator", "See explanatory notes.")
        if record["kind"] == "simple_window":
            record.update(record.pop("properties"))
        return record

    def state_inputs(self, archetype_id="mf_se02", renovation_state="existing"):
        """Resolve a complete role recipe for the nominal builder."""
        archetype = self.archetypes[archetype_id]
        state = deepcopy(archetype["states"][renovation_state])
        materials = {mid: self.resolve_material(mid) for mid in self.materials}
        assemblies, sources = self.assemblies, self.sources
        elements, thickness, framing, mids = {}, [], [], set()
        for role, aid in state["assemblies"].items():
            assembly = assemblies[aid]
            if role == "WINDOW":
                p = materials[assembly["material_id"]]["properties"]
                elements[role] = {field: p[field] for field in ("u_value", "shgc", "vt", "boverket_id")}
                mids.add(assembly["material_id"])
            else:
                elements[role] = {"components": assembly["components"]}
                for component in assembly["components"]:
                    for layer in component["layers"]:
                        mid = layer["material_id"]
                        mids.update([mid] if isinstance(mid, str) else mid)
                thickness.extend({"role": role, **c} for c in assembly.get("thickness_constraints", []))
                framing.extend({"role": role, **c} for c in assembly.get("framing_constraints", []))
        opaque = {mid for mid in mids if materials[mid]["kind"] == "opaque"}
        reviews = {mid: self._material(mid) for mid in sorted(opaque)}
        review = self.review(archetype_id, renovation_state)
        definition = {
            **state, "format_version": 1, "source_recipe": "resolved_recipe", "element_patches": {},
            "included_roles": list(elements), "layer_constraints": thickness, "framing_constraints": framing,
            "material_reviews": reviews, "sources": {sid: sources[sid] for sid in state["source_ids"]},
            "assumptions": review["notes"], "pending": list(dict.fromkeys(c["note"] for c in review["open_caveats"])),
            "review_annotations": review,
        }
        snapshot = {
            "format_version": 1, "resolved_recipe": {**state["identity"], "elements": elements},
            "materials": {mid: materials[mid]["properties"] for mid in opaque},
            "sources": definition["sources"],
        }
        return definition, snapshot

    def existing_inputs(self, archetype_id="mf_se02"):
        return self.state_inputs(archetype_id, "existing")

    def compose(self, archetype_id, *, state=None):
        """Build the recorded physical composition without assessing its targets.

        Parameters
        ----------
        archetype_id : str
            Registry identifier, including explicitly selected source variants.
        state : str or None
            Recorded configuration. None selects Existing before SE.07; SE.07
            accepts None only. Unknown identifiers or states raise KeyError.

        Returns
        -------
        Archetype
            Shared immutable authoring objects, with stable material identities,
            source references and review notes. Operating/system/envelope
            sections stay absent; no physical defaults are selected here.

        Notes
        -----
        Uses this already-loaded registry only. Supplied physical values are
        validated by the shared constructors; target tolerances, drift and
        calibration acceptance are separate assessment concerns. No thickness
        or material property is retuned, and no catalogue or service is loaded.
        Call review() for structured evidence and the existing calibration API
        for explicit target assessment. Raises ValueError for invalid physical
        values or a renovation state requested for SE.07.
        """
        from .usecases.build_archetype import build_archetype

        era = self.archetypes[archetype_id]["era"]
        if era == "SE.07" and state is not None:
            raise ValueError("SE.07 has no renovation states")
        if era != "SE.07" and state is None:
            state = "existing"
        definition, snapshot = self.state_inputs(archetype_id, state)
        spec = deepcopy(snapshot[definition["source_recipe"]])
        spec.update(definition["identity"])
        for role, patch in definition["element_patches"].items():
            spec["elements"][role] = deepcopy(patch)
        spec["elements"] = {role: spec["elements"][role]
                            for role in definition["included_roles"]}

        def digest(value):
            encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
            return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

        materials = {}
        for mid, properties in snapshot["materials"].items():
            materials[mid] = _opaque_material(properties)
        archetype = build_archetype(spec, materials=materials)
        revision = digest({"definition": definition, "source_snapshot": snapshot})
        construction = replace(archetype.construction_set,
            version_id=uuid5(NAMESPACE_URL, f"epsm_data:layered:{revision}"))
        # Text references retain the registered identity and its complete loaded
        # description, so portable exchange needs no registry/source lookup.
        references = tuple(f"{sid}: " + "; ".join(f"{key}={value}" for key, value in record.items())
                           for sid, record in definition["sources"].items())
        review = definition["review_annotations"]
        notes = [*definition["assumptions"]]
        if definition.get("scope_note"):
            notes.append(definition["scope_note"])
        for annotation in review["record_annotations"]:
            owner = f"{annotation['owner_type']} {annotation['owner_id']}"
            notes.extend(f"{owner}: {note}" for note in annotation["notes"])
        for caveat in review["caveats"]:
            owner = f"{caveat['owner_type']} {caveat['owner_id']} ({caveat['id']})"
            context = f"{caveat.get('scope', 'catalogue')}; topic={caveat['topic']}"
            if caveat.get("source"):
                context += f"; source={caveat['source']}"
            note = (f"{owner} {caveat['status']} {caveat['severity']} "
                    f"[{context}]: {caveat['note']}")
            if caveat.get("resolution"):
                note += f" Resolution: {caveat['resolution']}"
            notes.append(note)
        result = archetype.with_changes(construction_set=construction,
            source_references=references, notes=tuple(dict.fromkeys(notes)))
        logger.debug("Composed physical archetype %s (%s)", archetype_id, state)
        return result

    def target_catalogue(self, archetype_id, catalogue):
        """Resolve a named source variant's own LoD1 targets without changing slots."""
        archetype = self.archetypes[archetype_id]
        if archetype.get("catalogue_assignment", "canonical") == "canonical":
            return catalogue
        state = archetype["states"]["existing"]
        for role, reference in state.get("variant_overrides", {}).items():
            catalogue = catalogue.with_override(archetype["category"], role, reference)
        return catalogue

    def renovation_inputs(self, archetype_id="mf_se02"):
        archetype = self.archetypes[archetype_id]
        _, existing = self.existing_inputs(archetype_id)
        existing_ids = set(existing["materials"])
        assemblies, sources = self.assemblies, self.sources
        all_ids, states, source_ids = set(), {}, set()
        for name in ("standard", "advanced"):
            state = deepcopy(archetype["states"][name])
            operations = []
            window = None
            source_ids.update(state["source_ids"])
            for operation in state["operations"]:
                assembly = assemblies[operation["assembly_id"]]
                op = {**operation, "note": " ".join(operation["notes"])}
                if op["action"] == "replace_window":
                    window = self._material(assembly["material_id"])
                    op["material"] = "window"
                else:
                    component = assembly["components"][0]
                    op["shearing_layer"] = component["shearing_layer"]
                    op["layers"] = []
                    for layer in component["layers"]:
                        mid = layer["material_id"]
                        all_ids.update([mid] if isinstance(mid, str) else mid)
                        op["layers"].append({**layer, "thickness_mm": layer["thickness"] * 1000})
                operations.append(op)
            states[name] = {**state, "window": window, "operations": operations,
                            "review_annotations": self.review(archetype_id, name)}
        return {
            "format_version": 1, "category": archetype["category"], "era": archetype["era"],
            "base_revision": states["standard"]["base_revision"],
            "tolerance_percent": states["standard"]["tolerance_percent"],
            "scope_note": states["standard"]["scope_note"],
            "sources": {sid: sources[sid] for sid in source_ids},
            "materials": {mid: self._material(mid) for mid in sorted(all_ids - existing_ids)},
            "reused_materials": sorted(all_ids & existing_ids), "states": states,
        }

    def summary(self):
        caveats = {(c["owner_type"], c["owner_id"], c["id"]): c
                   for aid, a in self.archetypes.items() for state in a["states"]
                   for c in self.caveats(aid, state)}
        return {"materials": len(self.materials), "assemblies": len(self.assemblies),
                "archetypes": len(self.archetypes),
                "states": sum(len(a["states"]) for a in self.archetypes.values()),
                "open_caveats": sum(c["status"] == "open" for c in caveats.values())}

    def lod2_completeness(self, *, catalogue=None):
        """Check detailed recipes, source links, calibration and modelling readiness.

        Counts recipe coverage separately from accepted LoD2 completeness. The
        simple whole-window representation is supported; panes are not required,
        but unresolved optical evidence and boundary modelling remain explicit.
        No layers are scaled into other eras or building categories.
        """
        from .layered import _load_calibrated_archetype

        catalogue = catalogue if catalogue is not None else _load_parametric_catalogue()
        rows, covered, complete = [], set(), set()
        for aid, archetype in self.archetypes.items():
            for state, variant in archetype["states"].items():
                target_catalogue = self.target_catalogue(aid, catalogue)
                slots = target_catalogue.search(category=archetype["category"], era=archetype["era"],
                                                renovation_state=state)
                assignment = archetype.get("catalogue_assignment", "canonical")
                slot_ids = {s.slot_id for s in slots} if assignment == "canonical" else set()
                mids = set(self.active_material_ids(aid, state))
                pending = sorted(mid for mid in mids if self.materials[mid]["mapping_status"] == "pending")
                non_products = sorted(mid for mid in mids if self.materials[mid]["mapping_status"] == "not_applicable")
                hb_ids = {self._data["materials"]["materials"][mid]["honeybee_id"] for mid in mids}
                caveats = [c for c in self.caveats(aid, state, status="open")
                           if not (c["owner_type"] == "material" and c["owner_id"] not in mids)
                           and not (c["owner_type"] == "honeybee" and c["owner_id"] not in hb_ids)]
                blockers = [c for c in caveats if c["severity"] == "blocking"
                            and c.get("scope", "catalogue") == "catalogue"]
                reasons, slot_checks = [], []
                checks = {"construction_builder_supported": False}
                readiness = {"ground_validation": False, "carbon_assessment": False,
                             "simulation": False, "honeybee_nominal_export": False,
                             "core_nominal_export": False}
                generic_office = aid in {f"office_se{i:02d}" for i in range(1, 8)} and not (aid == "office_se05" and state == "existing" and variant.get("release_profile") not in ("lod2-v1", "complete_recipe"))
                generic_school = aid in {f"school_se{i:02d}" for i in range(1, 8)}
                if ((archetype["category"] == "multi_family" and aid in {"mf_se02", "mf_1940", "mf_1950", "mf_se03", "mf_se04", "mf_se05", "mf_se06", "mf_se07"})
                        or aid in {f"sf_se{i:02d}" for i in range(1, 8)} or generic_office
                        or generic_school or (variant.get("release_profile") in ("lod2-v1", "complete_recipe") and aid.startswith("generic_se"))):
                    result = _load_calibrated_archetype(catalogue=catalogue, renovation_state=state,
                                                       detailed=self, archetype_id=aid)
                    report = result.report
                    checks = dict(report["lod2_checks"])
                    from .nominal import catalogue_lod2_checks

                    readiness = catalogue_lod2_checks(result)["readiness"]
                    for slot in slots:
                        live = {**slot.construction_set.properties, "infiltration": slot.infiltration}
                        same = all(live[p].to_dict() == variant["target_snapshot"][p] for p in live)
                        aligned = all(abs(100 * (report["elements"][p]["assembly_u"] / live[p].value - 1)) <= variant["tolerance_percent"] + 1e-10
                                      for p in ("roof", "external_wall", "intermediate_floor", "internal_wall", "window"))
                        slot_checks.append({"slot_id": slot.slot_id, "key": slot.key.to_dict(),
                                            "identical_state_targets": same, "nominal_u_alignment": aligned,
                                            "construction_revision": report["revision"]})
                    checks["classification_slots_validated"] = bool(slot_checks) and all(
                        r["identical_state_targets"] and r["nominal_u_alignment"] for r in slot_checks)
                    if aid in ({"mf_1940", "mf_se03", "mf_se04", "mf_se05", "mf_se06", "mf_se07"}
                               | {f"sf_se{i:02d}" for i in range(1, 8)}
                               | {f"office_se{i:02d}" for i in range(1, 8)}
                               | {f"school_se{i:02d}" for i in range(1, 8)}
                               | {f"generic_se{i:02d}" for i in range(1, 8)}) and state != "existing":
                        window_mid = self.assemblies[variant["assemblies"]["WINDOW"]]["material_id"]
                        product = self.materials[window_mid].get("selected_product")
                        target_uw = slots[0].properties["window"].value if slots else None
                        checks["selected_replacement_window"] = bool(
                            product and target_uw is not None
                            and abs(product["declared_uw"] / target_uw - 1) <= variant["tolerance_percent"] / 100 + 1e-12)
                        if not checks["selected_replacement_window"]:
                            reasons.append("Replacement window needs a named product with documented Uw within the state tolerance of its target.")
                    reasons.extend(result.to_nominal_dict()["limitations"])
                    if not checks["nominal_u_alignment"]:
                        reasons.append("Nominal mismatch or captured target/base revision drift; see calibration report.")
                elif (aid == "office_se05" and state == "existing") or aid == "school_fridhem":
                    from .office import _load_office_reference

                    if aid == "school_fridhem":
                        from .school import _load_school_reference
                        result = _load_school_reference(detailed=self, catalogue=catalogue)
                    else:
                        result = _load_office_reference(detailed=self, catalogue=catalogue)
                    checks = dict(result.report["lod2_checks"])
                    readiness = dict(result.report["readiness"])
                    reasons.extend(result.report["limitations"])
                    for slot in slots:
                        live = {**slot.construction_set.properties, "infiltration": slot.infiltration}
                        same = all(live[p].to_dict() == variant["target_snapshot"][p] for p in live)
                        slot_checks.append({"slot_id": slot.slot_id, "key": slot.key.to_dict(),
                                            "identical_state_targets": same, "nominal_u_alignment": all(
                                                abs(result.report["elements"][role]["assembly_u"] / live[prop].value - 1) <= variant["tolerance_percent"] / 100 + 1e-12
                                                for role, prop in result.report["role_properties"].items()),
                                            "construction_revision": result.report["revision"]})
                    checks["classification_slots_validated"] = bool(slot_checks) and all(
                        r["identical_state_targets"] and r["nominal_u_alignment"] for r in slot_checks)
                else:
                    reasons.append("No validated construction builder for this detailed archetype yet.")
                if pending:
                    reasons.append("Boverket references remain pending: " + ", ".join(pending))
                if not checks.get("thermal_and_optical_evidence_reviewed", False):
                    reasons.append("Thermal-property or window optical evidence still has open review caveats.")
                if blockers:
                    reasons.append("Open blocking catalogue review caveats remain; see blocking_caveats.")
                accepted = all(checks.values())
                covered.update(slot_ids)
                if accepted:
                    complete.update(slot_ids)
                rows.append({"archetype_id": aid, "category": archetype["category"], "era": archetype["era"],
                             "catalogue_assignment": assignment,
                             "state": state, "slots_with_recipe": len(slot_ids), "materials_used": len(mids),
                             "materials_with_both_references": len(mids) - len(pending) - len(non_products),
                             "non_product_materials": non_products,
                             "materials_requiring_boverket_reference": len(mids) - len(non_products),
                             "pending_boverket_references": pending, "checks": checks, "readiness": readiness,
                             "lod2_complete": accepted, "blocking_caveats": blockers,
                             "open_caveats": caveats, "slot_checks": slot_checks,
                             "accepted_evidence": [c for c in self.caveats(aid, state)
                                                   if c["status"] in {"accepted_assumption", "resolved"}],
                             "remaining": reasons})
        total = len(catalogue.slots)
        def revision(value):
            return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()

        return {"rule_version": 4 if all(
                    s.get("dataset_release") in ("epsm-lod2-v1.3", "epsm-lod2-v1.4", "current")
                    for a in self.archetypes.values() if a.get("catalogue_assignment", "canonical") == "canonical"
                    for s in a["states"].values()) else 3, "detailed_revision": revision(self._data),
                "catalogue_revision": revision(catalogue.to_dict()),
                "rule": "Catalogue LoD2: reviewed recipes, required product links, accepted thermal/optical evidence, archetype-role nominal alignment and validated nominal exports. Ground validation, carbon assessment and simulation readiness are separate.",
                "total_slots": total, "slots_with_layer_recipe": len(covered),
                "slots_without_layer_recipe": total - len(covered), "lod2_complete_slots": len(complete),
                "detailed_states": len(rows), "lod2_complete_states": sum(r["lod2_complete"] for r in rows),
                "states": rows}


def _carbon(resource, name):
    """Project official GWP-GHG AR4 modules without editing the source record."""
    gwp = [item for item in resource["DataItems"] if item["PropertyCode"] == "GWP-GHG AR4"]
    if any(item["PropertyUnitCode"] != "kg CO2 eq./kg" for item in gwp):
        raise ValueError("Unsupported Boverket carbon unit")
    modules = [v for item in gwp
               for v in item["DataValueItems"]]
    values = {v["DataModuleCode"]: v["Value"] for v in modules}
    if len(values) != len(modules):
        raise ValueError("Duplicate Boverket GWP module")
    return {
        "name": name, "resource_id": str(resource["ResourceId"]), "boverket_name": resource["Name"],
        "A1_A3_conservative": values["A1-A3 Conservative"], "A1_A3_typical": values["A1-A3 Typical"],
        "A4_transport": values["A4"], "A5_conservative": values["A5.1"],
        "conservative_factor": resource["ConservativeDataConversionFactor"],
        "conversion_factor": next((c["Value"] for c in resource.get("Conversions", [])
                                   if c["Field"] == "Volume" and c["Unit"] == "kg/m³"), None),
        "technical_service_life": resource["RefServiceLifeNormal"],
        "biogenic_carbon": resource.get("CalculatedBiogenicCarbon"),
    }


def _resolve_material(data, mid):
    link = deepcopy(data["materials"]["materials"][mid])
    hb = data["honeybee"]["materials"][link["honeybee_id"]]
    name = hb.get("display_name", hb["identifier"])
    bov = link["boverket_id"]
    resource = next((r for r in data["boverket"]["Resources"] if str(r["ResourceId"]) == bov), None)
    if bov is not None and resource is None:
        raise ValueError(f"{mid}: dangling Boverket reference")
    props = {"name": name, "boverket_id": bov,
             "embodied_carbon": _carbon(resource, name) if resource is not None else None}
    if hb["type"] == "EnergyMaterial":
        kind = "opaque"
        props.update({"json_id": link["json_id"], "material_type": hb["user_data"].get("epsm_material_type", hb["type"]),
                      **{f: hb[f] for f in ("roughness", "conductivity", "density", "specific_heat",
                                           "thermal_absorptance", "solar_absorptance", "visible_absorptance")}})
    elif hb["type"] == "EnergyWindowMaterialSimpleGlazSys":
        kind = "simple_window"
        props.update(u_value=hb["u_factor"], shgc=hb["shgc"], vt=hb["vt"])
    else:
        raise ValueError(f"{mid}: unsupported Honeybee type")
    meta = hb["user_data"]
    def digest(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()

    return {**link, "kind": kind, "honeybee_type": hb["type"], "properties": props,
            "honeybee_revision": digest(hb), "boverket_revision": digest(resource) if resource else None,
            **{f: deepcopy(meta[f]) for f in ("thermal_evidence", "optics_source", "optics_note") if f in meta}}


def _validate(data, catalogue):
    json.dumps(data, allow_nan=False)
    reference = catalogue.to_dict()
    sources = data["materials"].get("sources", {})
    if not isinstance(sources, dict) or not sources:
        raise ValueError("Detailed registry requires source records")
    for sid, source in sources.items():
        if (not isinstance(sid, str) or not sid.strip() or not isinstance(source, dict)
                or not any(isinstance(source.get(field), str) and source[field].strip()
                           for field in ("url", "locator", "note"))):
            raise ValueError("Source requires a stable ID and URL, locator or explanatory note")
    for name in REGISTRIES:
        root = data[name]
        version = 2 if name == "materials" else 1
        if root.get("format_version") != version:
            raise ValueError(f"Invalid {name} registry format")
        if name in {"materials", "assemblies", "archetypes"}:
            if not isinstance(root.get(name), dict) or not root[name]:
                raise ValueError(f"Invalid {name} registry records")
            if any(not isinstance(rid, str) or not rid.strip() for rid in root[name]):
                raise ValueError(f"{name}: record IDs must be nonempty strings")
        _annotations(root, name, sources)
    honeybee = data["honeybee"].get("materials")
    if not isinstance(honeybee, dict) or not honeybee:
        raise ValueError("Honeybee source requires material definitions")
    for hid, material in honeybee.items():
        if not isinstance(hid, str) or not hid.strip() or material.get("identifier") != hid:
            raise ValueError("Honeybee source key/identifier mismatch")
        meta = material["user_data"]
        _annotations(meta, hid, sources)
        if meta.get("definition_kind") not in {"custom", "stock"}:
            raise ValueError("Honeybee definition must declare custom or stock provenance")
        if material["type"] == "EnergyMaterial":
            _number(material["thickness"], "Honeybee prototype thickness")
        elif material["type"] != "EnergyWindowMaterialSimpleGlazSys":
            raise ValueError("Unsupported Honeybee source type")
    resources = data["boverket"].get("Resources")
    if not isinstance(resources, list) or not resources:
        raise ValueError("Boverket source requires resources")
    bov_ids = set()
    for resource in resources:
        rid = resource["ResourceId"]
        if isinstance(rid, bool) or not isinstance(rid, int) or rid <= 0 or str(rid) in bov_ids:
            raise ValueError("Duplicate or invalid Boverket ResourceId")
        bov_ids.add(str(rid))
        if resource["SourceVersion"] != data["boverket"]["Version"]:
            raise ValueError("Boverket source version mismatch")
        EmbodiedCarbon(**_carbon(resource, resource["Name"]))
    links = data["materials"]["materials"]
    identities = set()
    allowed = {"json_id", "honeybee_id", "boverket_id", "mapping_status", "source", "locator",
               "notes", "caveats", "candidate_boverket_id", "selected_product"}
    for mid, link in links.items():
        if set(link) - allowed:
            raise ValueError(f"{mid}: material links cannot contain properties or source definitions")
        identity = link["json_id"]
        if not isinstance(identity, str) or not identity.strip() or identity in identities:
            raise ValueError("Duplicate material identity")
        identities.add(identity)
        if link.get("honeybee_id") not in honeybee:
            raise ValueError(f"{mid}: dangling Honeybee reference")
        if link.get("boverket_id") is not None and link["boverket_id"] not in bov_ids:
            raise ValueError(f"{mid}: dangling Boverket reference")
        if "selected_product" in link:
            product = link["selected_product"]
            required = {"manufacturer", "model", "declared_uw", "performance_url", "performance_locator",
                        "epd_id", "epd_url", "boverket_id", "source_id"}
            if set(product) != required or any(not isinstance(product[k], str) or not product[k].strip()
                                               for k in required - {"declared_uw", "epd_id", "epd_url"}):
                raise ValueError(f"{mid}: invalid selected window product")
            epd = (product["epd_id"], product["epd_url"])
            if epd != (None, None) and any(not isinstance(v, str) or not v.strip() for v in epd):
                raise ValueError(f"{mid}: EPD identifier and URL must both be supplied or both null")
            if product["boverket_id"] != link["boverket_id"]:
                raise ValueError(f"{mid}: selected product/Boverket family mismatch")
            if product["source_id"] not in data["materials"]["sources"]:
                raise ValueError(f"{mid}: missing selected product source")
            _number(product["declared_uw"], f"{mid} selected product Uw")
    materials = {mid: _resolve_material(data, mid) for mid in links}
    assemblies, archetypes = data["assemblies"]["assemblies"], data["archetypes"]["archetypes"]
    identities = set()
    for mid, material in materials.items():
        _annotations(material, mid, sources)
        _source(material, mid, sources)
        props = material["properties"]
        if not isinstance(props.get("name"), str) or not props["name"].strip():
            raise ValueError(f"{mid}: material name is required")
        kind = material["kind"]
        status = material.get("mapping_status")
        carbon, bov = props.get("embodied_carbon"), props.get("boverket_id")
        if status in {"pending", "not_applicable"}:
            if carbon is not None or bov is not None:
                raise ValueError(f"{mid}: pending mapping must have null carbon and ID")
            if status == "not_applicable" and props.get("material_type") != "air_gap_equivalent":
                raise ValueError(f"{mid}: only non-product air-gap equivalents are exempt from mapping")
        elif status in {"matched_generic_family", "reviewed_proxy"}:
            if not bov or not carbon or carbon.get("resource_id") != bov:
                raise ValueError(f"{mid}: Boverket/carbon mismatch")
        else:
            raise ValueError(f"{mid}: invalid mapping status")
        if carbon is not None:
            EmbodiedCarbon(**carbon)
        if kind == "opaque":
            if material.get("honeybee_type") != "EnergyMaterial":
                raise ValueError(f"{mid}: invalid Honeybee type")
            Roughness(props["roughness"])
            for field in ("conductivity", "density", "specific_heat"):
                _number(props[field], f"{mid} {field}")
            if not 0.01 <= props["conductivity"] <= 400:
                raise ValueError(f"{mid}: unrealistic conductivity")
            for field in ("thermal_absorptance", "solar_absorptance", "visible_absorptance"):
                if _number(props[field], field, positive=False) > 1:
                    raise ValueError(f"{mid}: invalid absorptance")
            identity = props["json_id"]
            if not isinstance(identity, str) or not identity.strip() or identity in identities:
                raise ValueError("Duplicate material identity")
            identities.add(identity)
            if set(material.get("thermal_evidence", {})) != {"conductivity", "density", "specific_heat"}:
                raise ValueError(f"{mid}: missing thermal evidence")
            for evidence in material["thermal_evidence"].values():
                if evidence.get("source") not in sources or not evidence.get("note"):
                    raise ValueError(f"{mid}: dangling thermal evidence")
        elif kind == "simple_window":
            if material.get("honeybee_type") != "EnergyWindowMaterialSimpleGlazSys":
                raise ValueError(f"{mid}: invalid window representation")
            for field in ("u_value", "shgc", "vt"):
                value = _number(props[field], f"{mid} {field}")
                if field != "u_value" and value > 1:
                    raise ValueError(f"{mid}: invalid optical fraction")
            if material.get("optics_source") not in sources or not material.get("optics_note"):
                raise ValueError(f"{mid}: missing optics evidence")
        else:
            raise ValueError(f"{mid}: invalid material kind")
    for aid, assembly in assemblies.items():
        _annotations(assembly, aid, sources)
        role = BuildingElement(assembly["role"])
        if role == BuildingElement.WINDOW:
            mid = assembly.get("material_id")
            if mid not in materials or materials[mid]["kind"] != "simple_window":
                raise ValueError(f"{aid}: dangling window material")
            continue
        if not assembly.get("components"):
            raise ValueError(f"{aid}: missing components")
        for component in assembly["components"]:
            _annotations(component, aid, sources)
            ShearingLayer(component["shearing_layer"])
            if not component.get("layers"):
                raise ValueError(f"{aid}: missing layers")
            for layer in component["layers"]:
                _annotations(layer, aid, sources)
                depth = _number(layer["thickness"], "layer thickness")
                ids = layer["material_id"]
                ids = [ids] if isinstance(ids, str) else ids
                if not isinstance(ids, list) or not ids or len(ids) != len(set(ids)):
                    raise ValueError(f"{aid}: invalid material references")
                if any(mid not in materials or materials[mid]["kind"] != "opaque" for mid in ids):
                    raise ValueError(f"{aid}: dangling or nonopaque layer material")
                fractions = layer.get("area_fraction", [1] if len(ids) == 1 else [])
                if len(fractions) != len(ids):
                    raise ValueError(f"{aid}: missing composite fractions")
                for fraction in fractions:
                    if _number(fraction, "material fraction", positive=False) > 1:
                        raise ValueError(f"{aid}: invalid material fraction")
                if not math.isclose(sum(fractions), 1, abs_tol=0.001):
                    raise ValueError(f"{aid}: composite fractions do not sum to one")
                choices = layer.get("allowed_thickness_mm")
                if choices is not None:
                    _choices(choices, depth * 1000, "layer depth")
        calibration = assembly.get("calibration")
        if calibration is not None:
            addresses = calibration["linked_depths"]
            if not isinstance(addresses, list) or not addresses or len({tuple(a) for a in addresses}) != len(addresses):
                raise ValueError(f"{aid}: invalid linked calibration depths")
            for address in addresses:
                if len(address) != 2 or any(isinstance(i, bool) or not isinstance(i, int) or i < 0 for i in address):
                    raise ValueError(f"{aid}: invalid calibration address")
                try:
                    layer = assembly["components"][address[0]]["layers"][address[1]]
                except IndexError as exc:
                    raise ValueError(f"{aid}: dangling calibration depth") from exc
                _number(layer["source_thickness_m"], "source thickness")
                _choices(calibration["allowed_thickness_mm"], layer["thickness"] * 1000, "calibrated thickness")
        for field in ("thickness_constraints", "framing_constraints"):
            seen = set()
            for c in assembly.get(field, []):
                address = (c["component"], c["layer"])
                if address in seen or any(isinstance(i, bool) or not isinstance(i, int) or i < 0 for i in address):
                    raise ValueError(f"{aid}: duplicate/invalid constraint")
                seen.add(address)
                try:
                    layer = assembly["components"][address[0]]["layers"][address[1]]
                except IndexError as exc:
                    raise ValueError(f"{aid}: dangling constraint") from exc
                if field == "thickness_constraints":
                    _choices(c["allowed_thickness_mm"], layer["thickness"] * 1000, "thickness")
                else:
                    ids = layer["material_id"]
                    if not isinstance(ids, list) or c["material_id"] not in ids:
                        raise ValueError(f"{aid}: invalid framing material")
                    _choices(c["allowed_area_fractions"], layer["area_fraction"][ids.index(c["material_id"])], "framing", fraction=True)
    for aid, archetype in archetypes.items():
        _annotations(archetype, aid, sources)
        states = archetype.get("states", {})
        office = (aid, archetype["category"], archetype["era"]) == ("office_se05", "office", "SE.05")
        school_draft = (aid, archetype["category"], archetype["era"]) == ("school_fridhem", "school", "SE.02")
        historic_mf = aid in {"mf_1940", "mf_1950"} and archetype["category"] == "multi_family" and archetype["era"] == "SE.01"
        full_mf = (aid == "mf_1940" and historic_mf) or (
            aid in {"mf_se03", "mf_se04", "mf_se05", "mf_se06", "mf_se07"}
            and archetype["category"] == "multi_family"
            and archetype["era"] == aid.removeprefix("mf_").upper().replace("SE", "SE.")
        )
        full_sf = (aid in {f"sf_se{i:02d}" for i in range(1, 8)}
                   and archetype["category"] == "single_family"
                   and archetype["era"] == aid.removeprefix("sf_").upper().replace("SE", "SE."))
        full_office = (aid in {f"office_se{i:02d}" for i in range(1, 8)}
                       and archetype["category"] == "office"
                       and archetype["era"] == aid.removeprefix("office_").upper().replace("SE", "SE."))
        full_school = (aid in {f"school_se{i:02d}" for i in range(1, 8)}
                       and archetype["category"] == "school"
                       and archetype["era"] == aid.removeprefix("school_").upper().replace("SE", "SE."))
        office_existing_only = office and set(states) == {"existing"}
        assignment = archetype.get("catalogue_assignment", "canonical")
        if assignment not in {"canonical", "alternative"} or (
            assignment == "alternative" and not (historic_mf or school_draft)
        ):
            raise ValueError(f"{aid}: invalid catalogue assignment")
        if assignment == "alternative":
            overrides = states.get("existing", {}).get("variant_overrides", {})
            if overrides and set(overrides) != {"roof", "external_wall", "intermediate_floor", "internal_wall", "window"}:
                raise ValueError(f"{aid}: alternative needs all five variant targets when overriding")
            for role, override in overrides.items():
                if (override.get("era"), override.get("state")) != ("SE.01", "existing"):
                    raise ValueError(f"{aid}: invalid alternative target classification")
                _number(override.get("value"), f"{aid} variant {role}")
                if override.get("source") not in reference["sources"] or not override.get("locator"):
                    raise ValueError(f"{aid}: alternative target needs registered source and locator")
        draft = archetype.get("representation") == "source_layer_draft"
        if draft and not (office or school_draft):
            raise ValueError("Unsupported source-layer draft")
        if (school_draft or (office and not full_office) or (historic_mf and not full_mf)) and set(states) != {"existing"}:
            raise ValueError(f"{aid}: source-layer draft supports Existing only")
        if archetype["era"] == "SE.07" and set(states) != {None}:
            raise ValueError(f"{aid}: SE.07 requires one configuration and no renovation states")
        if archetype["era"] != "SE.07" and not (school_draft or office_existing_only or (office and not full_office) or (historic_mf and not full_mf)) and set(states) != {"existing", "standard", "advanced"}:
            raise ValueError(f"{aid}: requires exactly three renovation states")
        for name, state in states.items():
            _annotations(state, f"{aid}:{name}", sources)
            key = ArchetypeKey(**state["key"])
            if (key.category, key.era, key.renovation_state) != (archetype["category"], archetype["era"], name):
                raise ValueError(f"{aid}: state classification mismatch")
            _number(state["tolerance_percent"], "calibration tolerance")
            targets = state.get("target_snapshot", {})
            props = {"roof", "external_wall", "window", "ground_floor", "basement_wall",
                     "intermediate_floor", "internal_wall", "infiltration"}
            if set(targets) != props:
                raise ValueError(f"{aid}: target snapshot requires exactly eight properties")
            for prop, target in targets.items():
                _number(target["value"], f"target {prop}", positive=prop != "infiltration")
                if target.get("source") not in reference["sources"] or target.get("curve") not in reference["curves"]:
                    raise ValueError(f"{aid}: dangling target source/curve")
                expected_unit = "1/h" if prop == "infiltration" else "W/(m²K)"
                if target.get("unit") != expected_unit:
                    raise ValueError(f"{aid}: invalid target unit")
                EffectiveProperty(**target)
            if any(s not in sources for s in state["source_ids"]):
                raise ValueError(f"{aid}: dangling state source")
            if name == "existing" or state.get("release_profile") in ("lod2-v1", "complete_recipe") or ((full_mf or full_sf or full_office or full_school) and "assemblies" in state):
                refs = state["assemblies"]
                expected_roles = {"TOP_FLOOR", "EXT_WALL", "WINDOW", "GROUND_FLOOR", "BASEMENT_WALL",
                                  "INTERMEDIATE_FLOOR", "INT_WALL_NONLOADBEARING"}
                if school_draft:
                    expected_roles = {"ROOF", "EXT_WALL", "WINDOW", "GROUND_FLOOR",
                                      "INTERMEDIATE_FLOOR", "INT_WALL_NONLOADBEARING"}
                elif full_office:
                    expected_roles = {"ROOF", "EXT_WALL", "WINDOW", "GROUND_FLOOR",
                                      "INTERMEDIATE_FLOOR", "INT_WALL_NONLOADBEARING"}
                    if archetype["era"] == "SE.01":
                        expected_roles.add("BASEMENT_WALL")
                elif full_school:
                    expected_roles = {"TOP_FLOOR", "EXT_WALL", "WINDOW", "GROUND_FLOOR",
                                      "INTERMEDIATE_FLOOR", "INT_WALL_NONLOADBEARING"}
                    if archetype["era"] == "SE.01":
                        expected_roles.add("BASEMENT_WALL")
                if state.get("dataset_release") in ("epsm-lod2-v1.3", "epsm-lod2-v1.4", "current"):
                    expected_roles.add("BASEMENT_WALL")
                if set(refs) != expected_roles:
                    raise ValueError(f"{aid}: Existing must contain the declared construction roles")
                if "base_state" in state:
                    raise ValueError("Full state recipe cannot inherit a renovation state")
            else:
                if state.get("base_state") != "existing":
                    raise ValueError("Renovated variants must derive directly from Existing")
                if not isinstance(state.get("base_revision"), str) or not state["base_revision"]:
                    raise ValueError("Renovation requires captured base revision")
                refs = {}
                for op in state["operations"]:
                    _annotations(op, aid, sources)
                    if op["role"] in refs or op["source"] not in sources or not op.get("source_measure"):
                        raise ValueError("Duplicate or unsourced renovation operation")
                    refs[op["role"]] = op["assembly_id"]
                    if op["action"] in {"add_component", "replace_exterior"}:
                        _number(op["source_thickness_mm"], "source measure depth")
                        if op.get("position") not in {"outside", "before_inside_finish"}:
                            raise ValueError("Invalid renovation layer position")
                        if len(assemblies.get(op["assembly_id"], {}).get("components", [])) != 1:
                            raise ValueError("Renovation addition must reference one component assembly")
                        if op["action"] == "replace_exterior":
                            count = op.get("remove_components")
                            original = assemblies[states["existing"]["assemblies"][op["role"]]]
                            if (op["role"] != "EXT_WALL" or op["position"] != "outside"
                                    or isinstance(count, bool) or not isinstance(count, int)
                                    or not 0 < count < len(original["components"])):
                                raise ValueError("Invalid exterior-component removal")
                    elif op["action"] != "replace_window" or op["role"] != "WINDOW":
                        raise ValueError("Invalid renovation operation")
                unchanged = state["unchanged_roles"]
                if (len(unchanged) != len(set(unchanged)) or set(refs) & set(unchanged)
                        or set(refs) | set(unchanged) != set(states["existing"]["assemblies"])):
                    raise ValueError("Every role must be modified or explicitly unchanged")
            for role, assembly_id in refs.items():
                BuildingElement(role)
                if assembly_id not in assemblies or assemblies[assembly_id]["role"] != role:
                    raise ValueError(f"{aid}: dangling or wrong-role assembly")
        if school_draft:
            from .school import validate_school_evidence

            validate_school_evidence(states["existing"], assemblies)
        if office:
            from .office import validate_office_evidence

            validate_office_evidence(states["existing"])


def _choices(choices, selected, label, *, fraction=False):
    if not isinstance(choices, list) or not choices or len(set(choices)) != len(choices):
        raise ValueError(f"Invalid {label} choices")
    for choice in choices:
        if _number(choice, label, positive=not fraction) > 1 and fraction:
            raise ValueError("Invalid framing fraction")
    if not any(math.isclose(selected, value, rel_tol=0, abs_tol=1e-8) for value in choices):
        raise ValueError(f"Selected {label} outside practical choices")


@logged_operation("catalogue.detailed.load")
def _load_detailed_catalogue(path=None, *, catalogue=None) -> DetailedCatalogue:
    """Load the five bundled files, a caller's registry directory or registry file.

    No network, archive, SQL or historical-snapshot reads. A file path must be
    one of the five canonical JSON names; all siblings are loaded.
    """
    if path is None:
        root = files("epsm_data.datasets.layered")
    else:
        target = Path(path)
        if target.is_dir():
            root = target
        elif target.name in {f"{name}.json" for name in REGISTRIES}:
            root = target.parent
        else:
            raise ValueError("path must be a registry directory or a canonical registry/source JSON")
    data = {}
    for name in REGISTRIES:
        with root.joinpath(f"{name}.json").open(encoding="utf-8") as handle:
            data[name] = json.load(handle, object_pairs_hook=_unique_object, parse_constant=_nonfinite)
    for aid, archetype in data["archetypes"]["archetypes"].items():
        if archetype.get("era") == "SE.07":
            if "states" in archetype or "configuration" not in archetype:
                raise ValueError(f"{aid}: SE.07 must define a configuration, not renovation states")
            archetype["states"] = {None: archetype.pop("configuration")}
    try:
        _validate(data, catalogue if catalogue is not None else _load_parametric_catalogue())
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"Invalid detailed registry structure: {exc}") from exc
    return DetailedCatalogue(deepcopy(data))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, help="Registry directory or one canonical registry JSON")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--check", action="store_true", help="Validate registry structure and references, not physics readiness")
    parser.add_argument("--caveats", action="store_true", help="Show caveat ownership/history for a state")
    parser.add_argument("--lod2", action="store_true", help="Report LoD2 recipe coverage and readiness, not just nominal U calibration")
    parser.add_argument("--state", choices=("existing", "standard", "advanced"), default="existing")
    parser.add_argument("--catalogue", type=Path, help="LoD1 catalogue JSON; omit for live defaults")
    args = parser.parse_args()
    thermal = _load_parametric_catalogue(args.catalogue)
    catalogue = _load_detailed_catalogue(args.path, catalogue=thermal)
    if args.lod2:
        report = catalogue.lod2_completeness(catalogue=thermal)
        if args.summary:
            report["states"] = [{k: v for k, v in row.items() if k not in {"blocking_caveats", "open_caveats", "accepted_evidence", "slot_checks"}}
                                for row in report["states"]]
        print(json.dumps(report, indent=2, ensure_ascii=False))
    elif args.caveats:
        print(json.dumps(catalogue.caveats(state=args.state), indent=2, ensure_ascii=False))
    elif args.summary:
        print(json.dumps(catalogue.summary(), indent=2))
    else:
        print("Detailed registries validated; construction/physics acceptance is a separate check.")


if __name__ == "__main__":
    main()
