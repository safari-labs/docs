"""
Footprint Controller — Thin adapter between HTTP request params and domain logic.
All grid calculations live in server2.domain.footprint.
"""
from ..models import FootprintModel, AntennaModel
from ..domain.footprint import compute_footprint_grid


class FootprintController:
    """Controller for footprint operations"""

    def __init__(self, footprint_model: FootprintModel, antenna_model: AntennaModel):
        self.footprint_model = footprint_model
        self.antenna_model = antenna_model

    def calculate(self, lat: float, lon: float, alt: float,
                  pitch: float, roll: float, yaw: float,
                  frequency_mhz: float, tx: str, grid_n: int,
                  grid_scale: float = 1.0,
                  rf_budget: dict = None,
                  gs_lat: float = None, gs_lon: float = None,
                  gs_alt: float = None, rx_key: str = None) -> tuple:
        """Calculate footprint grid — delegates to domain layer."""
        from ..domain.antenna_registry import AntennaRegistry

        if not AntennaRegistry.is_valid(tx):
            return {"error": "Unknown antenna"}, 400

        result = compute_footprint_grid(
            lat=lat, lon=lon, alt=alt,
            pitch_deg=pitch, roll_deg=roll, yaw_deg=yaw,
            tx_key=tx,
            frequency_mhz=frequency_mhz,
            rf_budget=rf_budget,
            grid_n=grid_n,
            grid_scale=grid_scale,
            gs_lat=gs_lat, gs_lon=gs_lon, gs_alt=gs_alt,
            rx_key=rx_key,
        )

        if "error" in result:
            return result, 500

        return result, 200
