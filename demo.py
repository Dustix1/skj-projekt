import requests
import time
import json
import sys
import threading
import asyncio
import websockets
import msgpack

# Konfigurace
GATEWAY_URL = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000/broker"
TEST_USER = "dustix_presenter"
TEST_FILE = "choese.webp"

# Barvičky pro terminál
GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"
MAGENTA = "\033[95m"
RED = "\033[91m"

def print_step(msg):
    print(f"\n{BOLD}{BLUE}>>> {msg}{RESET}")

def print_cmd(cmd):
    print(f"{MAGENTA}$ {cmd}{RESET}")

def print_raw(data):
    print(f"{RESET}{json.dumps(data, indent=2)}")

def print_broker(msg):
    print(f"{YELLOW}[BROKER] {msg}{RESET}")

def print_info(msg):
    print(f"{CYAN}[i] {msg}{RESET}")

def print_success(msg):
    print(f"{GREEN}[✓] {msg}{RESET}")

# --- BROKER MONITOR THREAD ---
def broker_monitor():
    async def listen():
        try:
            async with websockets.connect(WS_URL) as ws:
                # Odebíráme všechna důležitá témata pro demo
                topics = ["storage.write", "storage.ack", "image.jobs", "image.done"]
                for t in topics:
                    await ws.send(msgpack.packb({"action": "subscribe", "topic": t}))
                
                while True:
                    raw = await ws.recv()
                    data = msgpack.unpackb(raw)
                    if data.get("action") == "deliver":
                        topic = data.get("topic")
                        payload = data.get("payload")
                        # Zkrátíme binární data pro výpis
                        display_payload = payload.copy()
                        if "data" in display_payload:
                            display_payload["data"] = f"<{len(payload['data'])} bytes of binary data>"
                        
                        print_broker(f"Téma: {BOLD}{topic}{RESET} | Zpráva: {json.dumps(display_payload)}")
        except Exception as e:
            pass

    asyncio.run(listen())

def run_demo():
    print(f"{BOLD}{YELLOW}=== HAYSTACK ARCHITEKTURA: LIVE DEMO ==={RESET}")
    print_info("Spouštím monitorování Message Brokeru na pozadí...")
    
    # Start monitoringu v samostatném vlákně
    monitor_thread = threading.Thread(target=broker_monitor, daemon=True)
    monitor_thread.start()
    time.sleep(1) # Čas na připojení

    # 1. Vytvoření Bucketů
    print_step("KROK 1: Vytváření nového bucketu")
    bucket_name = f"demo-bucket-{int(time.time())}"
    
    cmd = f"curl -X POST -H 'Content-Type: application/json' -d '{{\"name\": \"{bucket_name}\"}}' {GATEWAY_URL}/buckets/"
    print_cmd(cmd)
    
    resp = requests.post(f"{GATEWAY_URL}/buckets/", json={"name": bucket_name})
    if resp.status_code != 200:
        print(f"Chyba: {resp.text}")
        return
    bucket_id = resp.json()["id"]
    print_raw(resp.json())
    print_success(f"Bucket vytvořen! ID: {bucket_id}")

    # 2. Upload souboru
    print_step("KROK 2: Asynchronní upload (Event-Driven)")
    print_info(f"Nahrávám soubor {TEST_FILE}...")
    
    cmd = f"curl -X POST -F 'file=@{TEST_FILE}' -F 'user_id={TEST_USER}' -F 'bucket_id={bucket_id}' {GATEWAY_URL}/files/upload"
    print_cmd(cmd)
    
    with open(TEST_FILE, "rb") as f:
        files = {"file": (TEST_FILE, f, "image/webp")}
        data = {"user_id": TEST_USER, "bucket_id": bucket_id}
        resp = requests.post(f"{GATEWAY_URL}/files/upload", files=files, data=data)
    
    upload_data = resp.json()
    file_id = upload_data["id"]
    print_info(f"Odpověď od S3 Gateway (HTTP {resp.status_code} Accepted)")
    print_raw(upload_data)
    print(f"{YELLOW}[!] Pozor: Status je 'uploading', volume_id a offset jsou null.{RESET}")

    # 3. Čekání na ACK od Haystacku
    print_step("KROK 3: Čekání na potvrzení (ACK) od Haystack Storage Node")
    print_info("Sledujte [BROKER] výpis nahoře. Měly by se objevit zprávy 'storage.write' a 'storage.ack'.")
    
    ready = False
    for i in range(10):
        time.sleep(1)
        resp = requests.get(f"{GATEWAY_URL}/buckets/{bucket_id}/objects/")
        objs = resp.json()
        f_meta = next((o for o in objs if o["id"] == file_id), None)
        
        if f_meta and f_meta["status"] == "ready":
            print_success(f"Zápis potvrzen!")
            print_raw(f_meta)
            ready = True
            break
        else:
            print_info(f"Pokus {i+1}: Čekám na ACK...")
    
    if not ready:
        print("Demo selhalo: ACK nedorazil včas.")
        return

    # 4. Image Worker
    print_step("KROK 4: Image Processing (Image Worker Node)")
    print_info("Posílám požadavek na operaci 'negative' přes Message Broker...")
    
    cmd = f"curl -X POST -H 'user-id: {TEST_USER}' -H 'Content-Type: application/json' -d '{{\"operation\": \"negative\"}}' {GATEWAY_URL}/buckets/{bucket_id}/objects/{file_id}/process"
    print_cmd(cmd)
    
    process_resp = requests.post(
        f"{GATEWAY_URL}/buckets/{bucket_id}/objects/{file_id}/process",
        headers={"user-id": TEST_USER},
        json={"operation": "negative"}
    )
    print_raw(process_resp.json())
    
    print_info("Čekám na workerovy zprávy 'image.jobs' a následný upload...")
    processed_id = None
    for i in range(15):
        time.sleep(1.5)
        resp = requests.get(f"{GATEWAY_URL}/buckets/{bucket_id}/objects/")
        objs = resp.json()
        processed = next((o for o in objs if o["filename"].startswith("negative_")), None)
        if processed and processed["status"] == "ready":
            processed_id = processed["id"]
            print_success("Obrázek zpracován!")
            print_raw(processed)
            break
        else:
            print_info(f"Pokus {i+1}: Čekám na workera...")

    # 5. Finální stažení
    if processed_id:
        print_step("KROK 5: Stažení výsledku (Proxy Read)")
        print_info("Gateway nyní čte přímo ze správného offsetu v binárním svazku...")
        
        cmd = f"curl -o result.webp '{GATEWAY_URL}/files/{processed_id}?user_id={TEST_USER}'"
        print_cmd(cmd)
        
        dl_url = f"{GATEWAY_URL}/files/{processed_id}?user_id={TEST_USER}"
        resp = requests.get(dl_url)
        if resp.status_code == 200:
            with open("presentation_result.webp", "wb") as out:
                out.write(resp.content)
            print_success("Soubor stažen jako 'presentation_result.webp'!")
    
    print(f"\n{BOLD}{GREEN}=== DEMO DOKONČENO ÚSPĚŠNĚ ==={RESET}")
    print_info("Všechny kroky proběhly přes Message Broker a binární úložiště Haystack.")
    time.sleep(2) # Necháme doznít poslední zprávy z brokeru

if __name__ == "__main__":
    run_demo()
