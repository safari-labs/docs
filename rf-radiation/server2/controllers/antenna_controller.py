"""
Antenna Controller — Thin adapter for antenna CRUD.
Pattern computations live in server2.domain.antenna_registry.
"""
from ..models import AntennaModel
from ..domain.antenna_registry import AntennaRegistry, AntennaDefinition


class AntennaController:
    """Controller for antenna operations"""

    def __init__(self, antenna_model: AntennaModel):
        self.antenna_model = antenna_model

    def get_configs(self) -> dict:
        """Get all antenna configurations via domain registry."""
        return AntennaRegistry.all_configs()

    def add_custom(self, antenna_id: str, config: dict) -> tuple:
        """Add custom antenna to both legacy model and domain registry."""
        try:
            self.antenna_model.add_custom_antenna(antenna_id, config)
            # Also register in domain layer
            base = config.get("base_pattern", "dipole_half_wave")
            base_defn = AntennaRegistry.get(base)
            pattern_fn = base_defn.pattern_fn if base_defn else AntennaRegistry.get("dipole_half_wave").pattern_fn
            defn = AntennaDefinition(
                name=config.get("name", antenna_id),
                gain_dbi=float(config.get("gain_dbi", 2.2)),
                pattern_fn=pattern_fn,
                color=config.get("color", "#00d4ff"),
                description=config.get("desc", config.get("description", "")),
            )
            AntennaRegistry.register_custom(antenna_id, defn)
            return {"ok": True, "antenna": config}, 201
        except Exception as e:
            return {"error": str(e)}, 400

    def remove_custom(self, antenna_id: str) -> tuple:
        """Remove custom antenna from both legacy model and domain registry."""
        try:
            self.antenna_model.remove_custom_antenna(antenna_id)
            AntennaRegistry.unregister_custom(antenna_id)
            return {"ok": True}, 200
        except Exception as e:
            return {"error": str(e)}, 400

    def get_custom_antennas(self) -> dict:
        """Get all custom antennas."""
        return AntennaRegistry.get_custom_antennas()

    def is_valid(self, antenna_key: str) -> bool:
        """Check if antenna is valid."""
        return AntennaRegistry.is_valid(antenna_key)
