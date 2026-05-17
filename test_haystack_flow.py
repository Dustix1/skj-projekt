import requests
import time
import os

GATEWAY_URL = "http://127.0.0.1:8000"

def test_flow():
    print("[*] Vytvářím bucket...")
    resp = requests.post(f"{GATEWAY_URL}/buckets/", json={"name": "test-bucket"})
    if resp.status_code == 200:
        bucket_id = resp.json()["id"]
        print(f"[+] Bucket vytvořen: {bucket_id}")
    elif resp.status_code == 400:
        # Již existuje, zkusíme ho najít (nebo prostě použijeme ten co tam je)
        # Pro jednoduchost předpokládáme že se jmenuje test-bucket
        # Ale raději vytvoříme unikátní
        name = f"test-bucket-{int(time.time())}"
        resp = requests.post(f"{GATEWAY_URL}/buckets/", json={"name": name})
        bucket_id = resp.json()["id"]
        print(f"[+] Bucket vytvořen: {bucket_id}")
    else:
        print(f"[!] Chyba při vytváření bucketu: {resp.text}")
        return

    print("[*] Nahrávám soubor...")
    file_content = b"Toto je testovaci obsah souboru, ktery by mel byt v Haystacku."
    files = {"file": ("test.txt", file_content, "text/plain")}
    data = {"user_id": "test_user", "bucket_id": bucket_id}
    
    resp = requests.post(f"{GATEWAY_URL}/files/upload", files=files, data=data)
    if resp.status_code == 202:
        file_id = resp.json()["id"]
        print(f"[+] Soubor nahrán, ID: {file_id}, status: {resp.json()['status']}")
    else:
        print(f"[!] Chyba při uploadu: {resp.text}")
        return

    # Čekáme na status ready
    print("[*] Čekám na status ready...")
    for _ in range(10):
        time.sleep(1)
        resp = requests.get(f"{GATEWAY_URL}/buckets/{bucket_id}/objects/")
        objects = resp.json()
        f = next((o for o in objects if o["id"] == file_id), None)
        if f and f["status"] == "ready":
            print(f"[+] Soubor je READY! Volume: {f.get('volume_id')}, Offset: {f.get('offset')}")
            break
    else:
        print("[!] Soubor se nepřepnul do statusu ready včas.")
        return

    print("[*] Stahuji soubor...")
    resp = requests.get(f"{GATEWAY_URL}/files/{file_id}?user_id=test_user")
    if resp.status_code == 200:
        if resp.content == file_content:
            print("[+] Obsah souboru souhlasí!")
        else:
            print(f"[!] Obsah souboru se liší! Očekáváno: {file_content}, Přijato: {resp.content}")
    else:
        print(f"[!] Chyba při stahování: {resp.text}")

    print("[*] Testuji Soft Delete...")
    resp = requests.delete(f"{GATEWAY_URL}/files/{file_id}?user_id=test_user")
    print(f"[+] Soft Delete výsledek: {resp.json()['message']}")

    resp = requests.get(f"{GATEWAY_URL}/buckets/{bucket_id}/objects/")
    objects = resp.json()
    if any(o["id"] == file_id for o in objects):
         print("[!] Soubor je stále vidět v listingu!")
    else:
         print("[+] Soubor už není v listingu.")

    # Kompakce
    print("[*] Spouštím kompakci pro volume 1...")
    # Musíme počkat aby se data stihla zapsat a zavřít (i když u nás je to hned)
    os.system("./.venv/bin/python3 compact.py 1")
    
    # Po kompakci by už soubor neměl být dohledatelný (protože je smazaný), 
    # ale pokud bychom měli jiný nesmazaný soubor, ten by měl fungovat.
    
    # Zkusíme nahrát druhý soubor, nechat ho být, a pak kompakci
    print("[*] Nahrávám druhý soubor (pro test kompakce)...")
    file_content2 = b"Druhy soubor, ktery prezije kompakci."
    files2 = {"file": ("test2.txt", file_content2, "text/plain")}
    resp = requests.post(f"{GATEWAY_URL}/files/upload", files=files2, data=data)
    file_id2 = resp.json()["id"]
    
    # Čekáme na ready
    time.sleep(2)
    
    print("[*] Spouštím kompakci znovu...")
    os.system("./.venv/bin/python3 compact.py 1")
    
    print("[*] Stahuji druhý soubor po kompakci...")
    resp = requests.get(f"{GATEWAY_URL}/files/{file_id2}?user_id=test_user")
    if resp.status_code == 200 and resp.content == file_content2:
        print("[+] Druhý soubor funguje i po kompakci!")
    else:
        print(f"[!] Druhý soubor po kompakci selhal: {resp.status_code}")

if __name__ == "__main__":
    test_flow()
