"""
RF Budget Controller - Manages RF budget parameters
"""
from ..models import RFBudgetModel

class RFBudgetController:
    """Controller for RF budget operations"""
    
    def __init__(self, rf_budget_model: RFBudgetModel):
        self.rf_budget_model = rf_budget_model

    def get_all(self) -> dict:
        """Get all RF budget parameters"""
        return self.rf_budget_model.get_all()

    def update(self, params: dict) -> tuple:
        """Update RF budget parameters"""
        try:
            self.rf_budget_model.update(params)
            return {"ok": True, "rf_budget": self.rf_budget_model.get_all()}, 200
        except Exception as e:
            return {"error": str(e)}, 400

    def reset(self) -> tuple:
        """Reset RF budget to defaults"""
        try:
            self.rf_budget_model.reset()
            return {"ok": True, "rf_budget": self.rf_budget_model.get_all()}, 200
        except Exception as e:
            return {"error": str(e)}, 400

    def get(self, key: str):
        """Get specific parameter"""
        return self.rf_budget_model.get(key)
