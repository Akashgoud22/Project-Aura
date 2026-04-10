import asyncio
import aiohttp
import websockets
import json

async def test_backend():
    print("Testing backend connection...")
    async with aiohttp.ClientSession() as session:
        # 1. Login or register
        creds = {"username": "testuser", "password": "testpassword", "email": "test@test.com"}
        # try register
        async with session.post('http://localhost:8000/api/auth/register', json=creds) as r:
            pass # ignore, might already exist
            
        # login
        async with session.post('http://localhost:8000/api/auth/login', json={"username": "testuser", "password": "testpassword"}) as r:
            if r.status != 200:
                print(f"Login failed: {r.status} {await r.text()}")
                return
            data = await r.json()
            token = data['access_token']
            print("Got token")
            
    # 2. connect WS
    ws_url = f"ws://localhost:8000/ws?token={token}"
    print(f"Connecting to WS: {ws_url}")
    try:
        async with websockets.connect(ws_url) as ws:
            print("WS connected!")
            
            # send text
            await ws.send(json.dumps({"type": "text", "content": "hello aura", "language": "en"}))
            print("Sent message, waiting for response")

            
            while True:
                msg = await ws.recv()
                data = json.loads(msg)
                print(f"Received msg type: {data.get('type')}")
                if data.get('type') == 'response':
                    print("Response:", data.get('text'))
                    break
    except Exception as e:
        print("WS error:", e)

if __name__ == "__main__":
    asyncio.run(test_backend())
