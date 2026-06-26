"""
Telemetry Controller - Manages telemetry data
"""
from ..models import TelemetryModel

class TelemetryController:
    """Controller for telemetry operations"""
    
    def __init__(self, telemetry_model: TelemetryModel):
        self.telemetry_model = telemetry_model

    def load_file(self, filepath: str) -> tuple:
        """Load telemetry from file"""
        try:
            success = self.telemetry_model.load_from_xlsx(filepath)
            if success:
                return {
                    "ok": True,
                    "message": f"Loaded {self.telemetry_model.get_count()} points"
                }, 200
            else:
                return {"error": "No valid data in file"}, 400
        except Exception as e:
            return {"error": str(e)}, 500

    def get_all(self) -> dict:
        """Get all telemetry data"""
        return {"data": self.telemetry_model.get_all()}

    def get_point(self, index: int) -> dict:
        """Get telemetry point"""
        point = self.telemetry_model.get_point(index)
        if point is None:
            return {"error": "Out of range"}, 400
        return point, 200

    def get_count(self) -> int:
        """Get telemetry count"""
        return self.telemetry_model.get_count()

    def clear(self):
        """Clear telemetry"""
        self.telemetry_model.clear()
