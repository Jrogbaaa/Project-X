from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.idea_match_service import get_idea_match_service

router = APIRouter(prefix="/idea-match", tags=["idea-match"])


class IdeaMatchRequest(BaseModel):
    brand: str = Field(..., min_length=1, max_length=500, description="Brand name or brief text")


@router.post("")
async def generate_idea_brief(
    request: IdeaMatchRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a structured creative advertising brief for a brand.

    Input: Brand name (e.g. "Nike") or a short brief.

    Pipeline:
    1. Extract structured brand attributes (category, archetype, growth goal, etc.)
    2. Deterministically select creative frameworks based on goal + archetype
    3. Retrieve analogous campaigns from the knowledge base (content-based filtering)
    4. Generate framework-driven creative ideas via GPT-4o
    5. Score and rank each idea by brand fit, originality, strategic relevance, feasibility

    Output: Structured IdeaBrief with 4-5 scored campaign ideas + one bold bet idea.
    """
    brand = request.brand.strip()
    if not brand:
        raise HTTPException(status_code=400, detail="Brand name cannot be empty")

    service = get_idea_match_service()
    try:
        brief = await service.generate(brand_input=brand, db=db)
        return brief
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Idea generation failed: {str(e)}")
