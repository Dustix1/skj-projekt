import requests
import os
import sys

GATEWAY_URL = "http://127.0.0.1:8000"

def compact_volume(volume_id: int):
    print(f"[*] Začínám kompakci svazku {volume_id}...")
    
    # 1. Získání seznamu objektů
    resp = requests.get(f"{GATEWAY_URL}/internal/volumes/{volume_id}/objects")
    if resp.status_code != 200:
        print(f"[!] Chyba při získávání objektů: {resp.text}")
        return
    
    objects = resp.json()
    if not objects:
        print("[*] Svazek je prázdný nebo obsahuje pouze smazané objekty.")
        return

    old_path = f"volume_{volume_id}.dat"
    new_path = f"volume_{volume_id}_compacted.dat"
    
    if not os.path.exists(old_path):
        print(f"[!] Soubor {old_path} neexistuje.")
        return

    try:
        new_offset = 0
        with open(old_path, "rb") as f_old, open(new_path, "wb") as f_new:
            for obj in objects:
                obj_id = obj["id"]
                offset = obj["offset"]
                size = obj["size"]
                
                # Čtení ze starého
                f_old.seek(offset)
                data = f_old.read(size)
                
                # Zápis do nového
                f_new.write(data)
                
                # Update Gateway
                update_resp = requests.patch(
                    f"{GATEWAY_URL}/internal/files/{obj_id}/location",
                    data={"volume_id": volume_id, "offset": new_offset}
                )
                
                if update_resp.status_code == 200:
                    print(f"[+] Přesunut objekt {obj_id}: {offset} -> {new_offset}")
                else:
                    print(f"[!] Chyba při updatu location pro {obj_id}: {update_resp.text}")
                
                new_offset += size
        
        # 4. Nahrazení starého souboru novým
        os.remove(old_path)
        os.rename(new_path, old_path)
        print(f"[*] Kompakce svazku {volume_id} dokončena.")
        
    except Exception as e:
        print(f"[!] Chyba během kompakce: {e}")
        if os.path.exists(new_path):
            os.remove(new_path)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Použití: python compact.py <volume_id>")
    else:
        compact_volume(int(sys.argv[1]))
