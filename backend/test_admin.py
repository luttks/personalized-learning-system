import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from uuid import UUID
from app.db.session import AsyncSessionLocal
from app.services.admin_subject_service import list_all_subjects, delete_user_subject, rename_user_subject

USER_ID = UUID("8add15ae-c407-48d2-a848-7ab6c23380a1")

async def test():
    async with AsyncSessionLocal() as session:
        # Kiểm tra ban đầu
        subjects_before = await list_all_subjects(session)
        print(f"\n=== BEFORE: {len(subjects_before)} subjects ===")
        for s in subjects_before:
            print(f"  - {s['subject']} (count={s['count']})")
        
        # Thử xóa 1 môn
        target = "Sinh học 12"
        print(f"\n>>> Deleting: '{target}'...")
        await delete_user_subject(session, USER_ID, target)
        
        # Kiểm tra sau khi xóa
        subjects_after = await list_all_subjects(session)
        print(f"\n=== AFTER DELETE: {len(subjects_after)} subjects ===")
        for s in subjects_after:
            print(f"  - {s['subject']} (count={s['count']})")
        
        deleted = not any(s['subject'] == target for s in subjects_after)
        print(f"\n>>> DELETE {'PASSED ✅' if deleted else 'FAILED ❌'}")
        
        # Thử rename 1 môn
        old_name = next((s['subject'] for s in subjects_after if 'Nâng cao' in s['subject']), None)
        if old_name:
            new_name = "TEST_RENAMED"
            print(f"\n>>> Renaming: '{old_name}' -> '{new_name}'...")
            await rename_user_subject(session, USER_ID, old_name, new_name)
            
            subjects_final = await list_all_subjects(session)
            renamed = any(s['subject'] == new_name for s in subjects_final)
            print(f">>> RENAME {'PASSED ✅' if renamed else 'FAILED ❌'}")
            
            # Restore
            print(f"\n>>> Restoring name back to '{old_name}'...")
            await rename_user_subject(session, USER_ID, new_name, old_name)
            print(">>> Restore done.")

if __name__ == "__main__":
    asyncio.run(test())
