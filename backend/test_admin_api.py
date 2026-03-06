import asyncio
import aiohttp
import json

async def test_admin():
    async with aiohttp.ClientSession() as session:
        # 1. Clear lockout
        async with session.post('http://localhost:8000/api/v1/auth/reset-lockout') as resp:
            print("Lockout reset:", await resp.json())
        
        # 2. Login as admin
        async with session.post(
            'http://localhost:8000/api/v1/auth/login',
            json={"email": "admin@kin.com", "password": "adminadmin"}
        ) as resp:
            data = await resp.json()
            if resp.status != 200:
                print("Login failed:", resp.status, data)
                return
            token = data['access_token']
            refresh = data['refresh_token']
        
        print("\n=== ADMIN LOGIN SUCCESSFUL ===")
        print(f"access_token = {token}")
        print(f"refresh_token = {refresh}")
        
        # 3. Get ALL devices (admin should see across families)
        headers = {'Authorization': f'Bearer {token}'}
        async with session.get('http://localhost:8000/api/v1/devices/', headers=headers) as resp:
            devices = await resp.json()
            print(f"\nDevices API status: {resp.status}")
            print(json.dumps(devices, indent=2))

if __name__ == '__main__':
    asyncio.run(test_admin())
