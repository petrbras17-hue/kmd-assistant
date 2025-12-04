import replicate
from app.core.config import settings

class RenovationService:
    def __init__(self):
        self.client = replicate.Client(api_token=settings.REPLICATE_API_TOKEN)
        self.model = "jagilley/controlnet-mlsd-1.5:69ed025f1b79a1d2488b928d3a77e314f10e797297c458f4432155c49442439a"

    def renovate(self, image_url: str, prompt: str) -> str:
        # Заглушка логики вызова
        return "https://replicate.com/api/models/predictions/output.jpg"
