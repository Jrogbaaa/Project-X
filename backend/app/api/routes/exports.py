from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import io

from app.core.database import get_db
from app.services.export_service import ExportService
from app.core.exceptions import ExportError

router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("/{search_id}/csv")
async def export_csv(
    search_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Export search results as CSV.

    Returns a downloadable CSV file with all influencer data from the search.
    """
    service = ExportService(db)
    try:
        csv_content = await service.export_to_csv(search_id)

        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=influencers_{search_id}.csv"
            }
        )
    except ExportError as e:
        raise HTTPException(status_code=404, detail=str(e.message))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/{search_id}/excel")
async def export_excel(
    search_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Export search results as Excel.

    Returns a downloadable Excel file (.xlsx) with formatted influencer data
    including headers, styling, and the original search query.
    """
    service = ExportService(db)
    try:
        excel_content = await service.export_to_excel(search_id)

        return Response(
            content=excel_content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename=influencers_{search_id}.xlsx"
            }
        )
    except ExportError as e:
        raise HTTPException(status_code=404, detail=str(e.message))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
