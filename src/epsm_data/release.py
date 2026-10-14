"""Compatibility entry points for integration code now owned by epsm."""


def core_inputs(*args, **kwargs):
    from epsm.catalogue_release import core_inputs as resolve
    return resolve(*args, **kwargs)


def apply_attic_ventilation(*args, **kwargs):
    from epsm.catalogue_release import apply_attic_ventilation as apply
    return apply(*args, **kwargs)
