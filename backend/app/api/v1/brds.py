import logging
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services import brd_service
from app.schemas.brd import BrdUploadResponse, BrdListResponse
from app.models.brd import BrdDocument
from app.models.rule import RuleSet, Rule, RuleSetStatus, RuleType
from app.models.test_case import TestCaseSuite
from app.pipeline.document_parser import parse_document
from app.pipeline.rule_extractor import extract_rules
from app.pipeline.rule_validator import validate_rules

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/brds", tags=["BRDs"])


@router.post("/upload", response_model=BrdUploadResponse)
async def upload_brd(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    if not file.filename.endswith((".pdf", ".docx")):
        raise HTTPException(400, "Only PDF and DOCX files are supported")
    brd = await brd_service.upload_brd(file, db)
    return BrdUploadResponse(
        id=str(brd.id),
        filename=brd.filename,
        file_type=brd.file_type.value,
        created_at=brd.created_at.isoformat(),
    )


@router.get("", response_model=list[BrdListResponse])
async def list_brds(db: AsyncSession = Depends(get_db)):
    brds = await brd_service.list_brds(db)
    return [BrdListResponse(
        id=str(b.id), filename=b.filename, file_type=b.file_type.value,
        created_at=b.created_at.isoformat(),
    ) for b in brds]


@router.get("/{brd_id}")
async def get_brd(brd_id: str, db: AsyncSession = Depends(get_db)):
    brd = await brd_service.get_brd(brd_id, db)
    if not brd:
        raise HTTPException(404, "BRD not found")
    return {
        "id": str(brd.id),
        "filename": brd.filename,
        "file_type": brd.file_type.value,
        "parsed_content": brd.parsed_content,
        "metadata": brd.metadata_json,
        "created_at": brd.created_at.isoformat(),
    }


@router.get("/{brd_id}/workflow")
async def get_brd_workflow(brd_id: str, db: AsyncSession = Depends(get_db)):
    """Get workflow status for a BRD: latest rule set and test case suite."""
    brd = await brd_service.get_brd(brd_id, db)
    if not brd:
        raise HTTPException(404, "BRD not found")

    # Get latest rule set for this BRD
    rs_result = await db.execute(
        select(RuleSet)
        .where(RuleSet.brd_document_id == brd.id)
        .order_by(RuleSet.version.desc())
        .limit(1)
    )
    rule_set = rs_result.scalar_one_or_none()

    rule_set_data = None
    test_case_suite_data = None

    if rule_set:
        rules_count = await db.execute(
            select(func.count()).select_from(Rule).where(Rule.rule_set_id == rule_set.id)
        )
        rule_set_data = {
            "id": str(rule_set.id),
            "status": rule_set.status.value,
            "rules_count": rules_count.scalar() or 0,
        }

        # Get latest test case suite for this rule set
        tc_result = await db.execute(
            select(TestCaseSuite)
            .where(TestCaseSuite.rule_set_id == rule_set.id)
            .order_by(TestCaseSuite.created_at.desc())
            .limit(1)
        )
        tc_suite = tc_result.scalar_one_or_none()
        if tc_suite:
            test_case_suite_data = {
                "id": str(tc_suite.id),
                "total_cases": tc_suite.total_cases,
                "cases_by_category": tc_suite.cases_by_category,
            }

    return {
        "brd_id": brd_id,
        "rule_set": rule_set_data,
        "test_case_suite": test_case_suite_data,
    }


@router.post("/{brd_id}/extract-rules")
async def extract_rules_from_brd(brd_id: str, db: AsyncSession = Depends(get_db)):
    """Extract rules from a BRD document using AI."""
    brd = await brd_service.get_brd(brd_id, db)
    if not brd:
        raise HTTPException(404, "BRD not found")

    # Parse document
    file_path = Path(brd.file_path)
    if not file_path.exists():
        raise HTTPException(404, "BRD file not found on disk")

    content = file_path.read_bytes()
    sections = parse_document(content, brd.filename)

    if not sections:
        raise HTTPException(422, "Could not parse document into sections")

    # Save parsed text to BRD record for UI visibility
    parsed_text = "\n\n".join(s.content for s in sections)
    brd.parsed_content = parsed_text
    brd.metadata_json = {
        "sections_count": len(sections),
        "total_chars": len(parsed_text),
        "section_titles": [s.title for s in sections],
    }

    # Extract rules using AI
    rule_definitions = extract_rules(sections)

    if not rule_definitions:
        raise HTTPException(422, "No rules could be extracted from the document")

    # Validate rules
    validated = validate_rules(rule_definitions)

    # Create rule set
    brd_name = brd.filename.replace(".docx", "").replace(".pdf", "")
    rule_set = RuleSet(
        brd_document_id=brd.id,
        name=f"Rules from {brd.filename}",
        description=f"Auto-extracted rules from {brd.filename}",
        status=RuleSetStatus.DRAFT,
    )
    db.add(rule_set)
    await db.flush()

    # Save individual rules
    for rd in rule_definitions:
        rule = Rule(
            rule_set_id=rule_set.id,
            rule_id=rd.rule_id,
            rule_name=rd.rule_name,
            description=rd.description,
            rule_type=RuleType(rd.rule_type.value if hasattr(rd.rule_type, 'value') else rd.rule_type),
            conditions=[c.model_dump() for c in rd.conditions],
            actions=[a.model_dump() for a in rd.actions],
            priority=rd.priority,
            confidence=rd.confidence,
            source_section=rd.source_section,
        )
        db.add(rule)

    await db.commit()

    return {
        "rule_set_id": str(rule_set.id),
        "rules_count": len(rule_definitions),
        "status": "DRAFT",
    }


@router.delete("/{brd_id}")
async def delete_brd(brd_id: str, db: AsyncSession = Depends(get_db)):
    deleted = await brd_service.delete_brd(brd_id, db)
    if not deleted:
        raise HTTPException(404, "BRD not found")
    return {"status": "deleted"}
