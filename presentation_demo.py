import requests
import time
import json
import sys

# Konfigurace
GATEWAY_URL = "http://127.0.0.1:8000"
TEST_USER = "dustix_presenter"
TEST_FILE = "choese.webp"

# Barvičky pro terminál
GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

def print_step(msg):
    print(f"\n{BOLD}{BLUE}>>> {msg}{RESET}")

def print_info(msg):
    print(f"{CYAN}[i] {msg}{RESET}")

def print_success(msg):
    print(f"{GREEN}[✓] {msg}{RESET}")

def run_demo():
    print(f"{BOLD}{YELLOW}=== HAYSTACK ARCHITEKTURA: LIVE DEMO ==={RESET}")

    # 1. Vytvoření Bucketů
    print_step("KROK 1: Vytváření nového bucketu")
    bucket_name = f"demo-bucket-{int(time.time())}"
    resp = requests.post(f"{GATEWAY_URL}/buckets/", json={"name": bucket_name})
    if resp.status_code != 200:
        print(f"Chyba: {resp.text}")
        return
    bucket_id = resp.json()["id"]
    print_success(f"Bucket vytvořen! ID: {bucket_id}")

    # 2. Upload souboru
    print_step("KROK 2: Asynchronní upload (Event-Driven)")
    print_info(f"Nahrávám soubor {TEST_FILE}...")
    
    with open(TEST_FILE, "rb") as f:
        files = {"file": (TEST_FILE, f, "image/webp")}
        data = {"user_id": TEST_USER, "bucket_id": bucket_id}
        resp = requests.post(f"{GATEWAY_URL}/files/upload", files=files, data=data)
    
    upload_data = resp.json()
    file_id = upload_data["id"]
    print_info(f"Odpověď od S3 Gateway (Status Code: {resp.status_code})")
    print(json.dumps(upload_data, indent=2))
    print(f"{YELLOW}[!] Všimněte si: status je 'uploading', volume_id a offset jsou null.{RESET}")

    # 3. Čekání na ACK od Haystacku
    print_step("KROK 3: Čekání na potvrzení (ACK) od Haystack Storage Node")
    ready = False
    for i in range(10):
        time.sleep(1)
        resp = requests.get(f"{GATEWAY_URL}/buckets/{bucket_id}/objects/")
        objs = resp.json()
        f_meta = next((o for o in objs if o["id"] == file_id), None)
        
        if f_meta and f_meta["status"] == "ready":
            print_success("Zápis dokončen!")
            print(json.dumps(f_meta, indent=2))
            print(f"{GREEN}[✓] Soubor je nyní ve Volume {f_meta['volume_id']} na offsetu {f_meta['offset']}.{RESET}")
            ready = True
            break
        else:
            print_info(f"Pokus {i+1}: Stále se nahrává...")
    
    if not ready:
        print("Demo selhalo: ACK nedorazil včas.")
        return

    # 4. Image Worker
    print_step("KROK 4: Image Processing (Image Worker Node)")
    print_info("Posílám požadavek na operaci 'negative' přes Message Broker...")
    
    process_resp = requests.post(
        f"{GATEWAY_URL}/buckets/{bucket_id}/objects/{file_id}/process",
        headers={"user-id": TEST_USER},
        json={"operation": "negative"}
    )
    print_info(f"Worker přijal úkol: {process_resp.json()['status']}")
    
    print_info("Čekám na zpracování a nový upload od Workera...")
    processed_id = None
    for i in range(15):
        time.sleep(1)
        resp = requests.get(f"{GATEWAY_URL}/buckets/{bucket_id}/objects/")
        objs = resp.json()
        # Hledáme soubor co začíná na negative_
        processed = next((o for o in objs if o["filename"].startswith("negative_")), None)
        if processed and processed["status"] == "ready":
            processed_id = processed["id"]
            print_success("Obrázek zpracován a uložen zpět do Haystacku!")
            print(json.dumps(processed, indent=2))
            break
        else:
            print_info(f"Čekám na workera... ({i+1})")

    # 5. Finální stažení
    if processed_id:
        print_step("KROK 5: Stažení výsledku (Proxy Read)")
        print_info("Gateway nyní čte přímo ze správného offsetu v binárním svazku...")
        dl_url = f"{GATEWAY_URL}/files/{processed_id}?user_id={TEST_USER}"
        resp = requests.get(dl_url)
        if resp.status_code == 200:
            with open("presentation_result.webp", "wb") as out:
                out.write(resp.content)
            print_success("Soubor stažen jako 'presentation_result.webp'!")
            print_info(f"Velikost: {len(resp.content)} bajtů")
    
    print(f"\n{BOLD}{GREEN}=== DEMO DOKONČENO ÚSPĚŠNĚ ==={RESET}")
    print_info("Všechny kroky proběhly přes Message Broker a binární úložiště Haystack.")

if __name__ == "__main__":
    run_demo()
