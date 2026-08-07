import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.models.user import User, UserRole
from app.core.security import hash_password
from sqlalchemy.future import select

async def seed_users():
    async with AsyncSessionLocal() as session:
        # Check if admin already exists
        result = await session.execute(select(User).where(User.email == "admin@example.com"))
        if result.scalar_one_or_none():
            print("Users already seeded.")
            return

        # Create Admin
        admin = User(
            full_name="Admin User",
            email="admin@example.com",
            password_hash=hash_password("admin123"),
            role=UserRole.ADMIN,
            is_active=True
        )
        # Create Student
        student = User(
            full_name="Student User",
            email="student@example.com",
            password_hash=hash_password("student123"),
            role=UserRole.STUDENT,
            is_active=True
        )
        session.add(admin)
        session.add(student)
        try:
            await session.commit()
            print("Users created successfully!")
            print("Admin: admin@example.com / admin123")
            print("Student: student@example.com / student123")
        except Exception as e:
            await session.rollback()
            print(f"Error creating users: {e}")

if __name__ == "__main__":
    asyncio.run(seed_users())
