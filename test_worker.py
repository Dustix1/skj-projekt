import asyncio
import websockets
import httpx
import json
import os
import uuid

API_URL = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000/broker"
USER_ID = "dustix_test_user"

LOCAL_IMAGE_PATH = "choese.webp" 

async def run_integration_test():
    print("--- Start Integračního Testu ---")
    
    # Pojistka, pokud soubor na disku neexistuje
    if not os.path.exists(LOCAL_IMAGE_PATH):
        print(f"[!] Chyba: Nemůžu najít soubor '{LOCAL_IMAGE_PATH}' na disku.")
        print(f"Prosím, vlož obrázek do stejné složky nebo uprav proměnnou LOCAL_IMAGE_PATH v kódu.")
        return

    async with httpx.AsyncClient() as client:
        # 1. Vytvoření bucketu s unikátním jménem
        bucket_name = f"test_images_{uuid.uuid4().hex[:8]}"
        print(f"[0/3] Vytvářím bucket: {bucket_name}")
        b_resp = await client.post(f"{API_URL}/buckets/", json={"name": bucket_name})
        
        if b_resp.status_code != 200:
            print(f"Chyba při vytváření bucketu: {b_resp.text}")
            return
            
        actual_bucket_id = b_resp.json()['id']

        # 2. Načtení reálného obrázku z disku
        print(f"[1/3] Načítám obrázek z disku: {LOCAL_IMAGE_PATH}...")
        with open(LOCAL_IMAGE_PATH, "rb") as f:
            img_bytes = f.read()

        # 3. Upload obrázku přes REST API
        print(f"      Nahrávám obrázek do bucketu {actual_bucket_id}...")
        filename = os.path.basename(LOCAL_IMAGE_PATH)
        content_type = 'image/jpeg' if filename.lower().endswith(('.jpg', '.jpeg')) else 'image/png'
        
        files = {'file': (filename, img_bytes, content_type)}
        data = {'user_id': USER_ID, 'bucket_id': actual_bucket_id}
        resp = await client.post(f"{API_URL}/files/upload", files=files, data=data)
        
        if resp.status_code != 200:
            print(f"Chyba při uploadu: {resp.text}")
            return
            
        file_id = resp.json()['id']
        print(f"[✓] Obrázek nahrán s ID: {file_id}")

    # 4. Připojení k brokeru jako posluchač na události dokončení
    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({"action": "subscribe", "topic": "image.done"}))
        
        # Seznam různých operací k otestování
        tasks = [
            {"operation": "negative"},
            {"operation": "mirror"},
            {"operation": "grayscale"},
            {"operation": "brighten", "params": {"value": 80}},
            {"operation": "crop", "params": {"top": 10, "bottom": 10, "left": 10, "right": 10}},
            {"operation": "negative"},
            {"operation": "mirror"},
            {"operation": "grayscale"},
            {"operation": "brighten", "params": {"value": 120}},
            {"operation": "crop", "params": {"top": 20, "bottom": 20, "left": 20, "right": 20}}
        ]

        # 5. Odeslání 10 úloh přes REST API
        print("\n[2/3] Odesílám 10 různých úloh na zpracování (všechny operace)...")
        async with httpx.AsyncClient() as client:
            for payload in tasks:
                headers = {"user-id": USER_ID}
                await client.post(f"{API_URL}/buckets/{actual_bucket_id}/objects/{file_id}/process", json=payload, headers=headers)
        
        # 6. Čekání na 10 potvrzení od workera
        print("\n[3/3] Čekám na zpracování Workerem...")
        completed = 0
        while completed < 10:
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=15.0)
                data = json.loads(response)
                
                if data.get("action") == "deliver" and data.get("topic") == "image.done":
                    completed += 1
                    status = data['payload']['status']
                    detail = data['payload']['detail']
                    op_name = data['payload']['operation']
                    print(f"  -> Worker dokončil úlohu {completed}/10 [{op_name}]. Status: {status} ({detail})")
                    
                    # Odeslání ACK brokeru
                    await ws.send(json.dumps({"action": "ack", "message_id": data["message_id"]}))
            except asyncio.TimeoutError:
                print(f"\n[X] Timeout! Worker nestihl zpracovat všechny úlohy. Dokončeno: {completed}/10")
                break

        if completed == 10:
            print("\n[✓] Integrační test úspěšně prošel! Všechny grafické operace v NumPy fungují.")

if __name__ == "__main__":
    asyncio.run(run_integration_test())