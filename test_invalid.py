import asyncio
import websockets
import httpx
import json
import io
import uuid
from PIL import Image

API_URL = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000/broker"

async def test_invalid_operation():
    print("--- Test Neplatné Operace ---")
    async with httpx.AsyncClient() as client:
        bucket_name = f"test_{uuid.uuid4().hex[:8]}"
        b_resp = await client.post(f"{API_URL}/buckets/", json={"name": bucket_name})
        bucket_id = b_resp.json()['id']

        img = Image.new('RGB', (10, 10), color='red')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)

        files = {'file': ('test.png', img_bytes, 'image/png')}
        data = {'user_id': "dustix", 'bucket_id': bucket_id}
        resp = await client.post(f"{API_URL}/files/upload", files=files, data=data)
        file_id = resp.json()['id']

    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({"action": "subscribe", "topic": "image.done"}))
        
        # POSÍLÁME NESMYSLNOU OPERACI
        print("[!] Odesílám úlohu: 'exploit-op'")
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{API_URL}/buckets/{bucket_id}/objects/{file_id}/process", 
                json={"operation": "exploit-op"}, 
                headers={"user-id": "dustix"}
            )
        
        response = await asyncio.wait_for(ws.recv(), timeout=5.0)
        data = json.loads(response)
        status = data['payload']['status']
        detail = data['payload']['detail']
        
        print(f"[✓] Odpověď Workera: Status: {status} | Detail: {detail}")
        if status == "processing_failed":
            print("Skvělé! Worker situaci ustál, nespadl a správně vrátil chybu.")

if __name__ == "__main__":
    asyncio.run(test_invalid_operation())