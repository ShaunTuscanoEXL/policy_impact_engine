import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import simulation_service
from app.services.export_service import generate_summary_csv, generate_segment_csv
from app.services.pdf_report import generate_pdf_report

router = APIRouter(prefix="/export", tags=["Export"])


async def _get_simulation_with_results(simulation_id: str, db: AsyncSession):
    """Fetch simulation and its first result, raising 404 if missing."""
    sim = await simulation_service.get_simulation(simulation_id, db)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")

    results = await simulation_service.get_simulation_results(simulation_id, db)
    if not results:
        raise HTTPException(
            status_code=404,
            detail="Simulation results not found. Run the simulation first.",
        )

    return sim, results[0]


@router.get("/simulation/{simulation_id}/csv")
async def export_csv(simulation_id: str, db: AsyncSession = Depends(get_db)):
    """Export simulation summary stats as a downloadable CSV."""
    sim, result = await _get_simulation_with_results(simulation_id, db)

    summary_stats = result.summary_stats or {}
    csv_content = generate_summary_csv(summary_stats)

    filename = f"simulation_{simulation_id}_summary.csv"
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/simulation/{simulation_id}/summary-csv")
async def export_segment_csv_endpoint(simulation_id: str, db: AsyncSession = Depends(get_db)):
    """Export segment analysis as a downloadable CSV."""
    sim, result = await _get_simulation_with_results(simulation_id, db)

    # Merge summary_stats and segment_analysis into one dict for the CSV generator
    stats = dict(result.summary_stats or {})
    if result.segment_analysis:
        stats["segment_breakdown"] = result.segment_analysis
    elif "segment_breakdown" not in stats:
        stats["segment_breakdown"] = {}

    csv_content = generate_segment_csv(stats)

    filename = f"simulation_{simulation_id}_segments.csv"
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/simulation/{simulation_id}/pdf")
async def export_pdf(simulation_id: str, db: AsyncSession = Depends(get_db)):
    """Generate and return a PDF report for the simulation."""
    sim, result = await _get_simulation_with_results(simulation_id, db)

    # Build a complete stats dict for the PDF
    stats = dict(result.summary_stats or {})
    if result.segment_analysis:
        stats["segment_breakdown"] = result.segment_analysis
    elif "segment_breakdown" not in stats:
        stats["segment_breakdown"] = {}
    if result.financial_impact:
        stats["financial_impact"] = result.financial_impact
    elif "financial_impact" not in stats:
        stats["financial_impact"] = {}

    date_str = (
        sim.completed_at.strftime("%Y-%m-%d %H:%M")
        if sim.completed_at
        else datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    )

    pdf_bytes = generate_pdf_report(
        simulation_name=sim.scenario_name,
        summary_stats=stats,
        date_str=date_str,
    )

    filename = f"simulation_{simulation_id}_report.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
