"""Element entity placeholder.

Expected responsibilities:
- Aggregation of components into envelope/internal wall elements.
- Boundary-condition metadata used by thermal module.
- Tabula/reference lookup keys and validation hooks.
"""


def define_element_model() -> None:
    """Implement element entity definitions and invariants."""
    raise NotImplementedError("Define element entities in domain/element.py")
