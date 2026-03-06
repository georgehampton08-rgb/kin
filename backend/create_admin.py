import asyncio
import uuid
from sqlalchemy import text
from app.db.session import AsyncSessionLocal
from app.core.auth import hash_password

async def create_admin():
    async with AsyncSessionLocal() as s:
        # Check if admin user exists
        res = await s.execute(text("SELECT id FROM users WHERE email = 'admin@kin.com'"))
        existing = res.fetchone()
        
        if existing:
            # Update password
            await s.execute(
                text("UPDATE users SET hashed_password = :h WHERE email = 'admin@kin.com'"),
                {"h": hash_password("adminadmin")}
            )
            print("Updated existing admin user password")
        else:
            # Create Family for completeness, though admin doesn't strictly need one
            fam_id = str(uuid.uuid4())
            await s.execute(
                text("INSERT INTO families (id, name, created_at) VALUES (:id, 'Admin Family', now())"),
                {"id": fam_id}
            )
            
            # Create user
            user_id = str(uuid.uuid4())
            await s.execute(
                text("""
                    INSERT INTO users (id, email, hashed_password, role, created_at)
                    VALUES (:id, 'admin@kin.com', :pw, 'admin', now())
                """),
                {"id": user_id, "pw": hash_password("adminadmin")}
            )
            
            # Create membership
            await s.execute(
                text("""
                    INSERT INTO family_memberships (id, family_id, user_id, role)
                    VALUES (:id, :fid, :uid, 'admin')
                """),
                {"id": str(uuid.uuid4()), "fid": fam_id, "uid": user_id}
            )
            print("Created new admin user: admin@kin.com / adminadmin")
        await s.commit()

if __name__ == "__main__":
    asyncio.run(create_admin())
