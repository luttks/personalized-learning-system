import asyncio
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os
import sys

sys.path.append(os.path.join(os.getcwd(), 'backend'))
load_dotenv('backend/.env')
DB_URL = os.getenv('DATABASE_URL')
if not DB_URL:
    print('DATABASE_URL not found')
    sys.exit(1)

from app.models.exam_analysis_model import ExamAnalysis

async def main():
    engine = create_async_engine(DB_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        result = await session.execute(
            select(ExamAnalysis).where(
                (ExamAnalysis.subject == 'Không xác định') | 
                (ExamAnalysis.subject == None) |
                (ExamAnalysis.subject == '')
            )
        )
        analyses = result.scalars().all()
        print(f"Found {len(analyses)} records to delete.")
        
        stmt = delete(ExamAnalysis).where(
            (ExamAnalysis.subject == 'Không xác định') | 
            (ExamAnalysis.subject == None) |
            (ExamAnalysis.subject == '')
        )
        await session.execute(stmt)
        await session.commit()
        print("Deleted.")

asyncio.run(main())
