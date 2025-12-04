from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.services.valuation import ValuationService
from app.services.renovation import RenovationService

router = APIRouter()

class ValuationRequest(BaseModel):
    area: float
    comparables: list[dict]

@router.post("/valuation/estimate")
def estimate_price(req: ValuationRequest):
    service = ValuationService()
    return service.estimate_price(req.area, req.comparables)

@router.post("/ai/renovate")
def renovate_room(image_url: str, style: str):
    service = RenovationService()
    return service.renovate(image_url, f"{style} interior")

@router.get("/voice/availability")
def check_availability(listing_id: str, date: str):
    return {"available": True, "slots": ["14:00", "16:00"]}
