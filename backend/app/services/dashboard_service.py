from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.brd import BrdDocument
from app.models.loan_record import LoanRecord
from app.models.test_case import TestCaseSuite


async def get_dashboard_stats(db: AsyncSession) -> dict:
    brd_count = await db.scalar(select(func.count(BrdDocument.id)))
    loan_count = await db.scalar(select(func.count(LoanRecord.id)))
    suite_count = await db.scalar(select(func.count(TestCaseSuite.id)))

    return {
        "total_brds": brd_count or 0,
        "total_loan_records": loan_count or 0,
        "total_test_suites": suite_count or 0,
    }
