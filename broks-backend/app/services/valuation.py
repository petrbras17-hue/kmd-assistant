import pandas as pd
from sklearn.ensemble import IsolationForest
from typing import List, Dict

class ValuationService:
    def __init__(self):
        self.outlier_detector = IsolationForest(contamination=0.05, random_state=42)

    def estimate_price(self, target_area: float, comps: List[Dict]) -> dict:
        if not comps:
            return {"error": "No data"}
        
        df = pd.DataFrame(comps)
        df['price_per_sqm'] = df['price'] / df['area']
        
        avg_sqm = df['price_per_sqm'].mean()
        recommended = avg_sqm * target_area
        
        return {
            "recommended_price": int(recommended),
            "range_min": int(recommended * 0.9),
            "range_max": int(recommended * 1.1)
        }
