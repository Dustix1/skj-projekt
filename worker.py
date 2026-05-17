import asyncio
import websockets
import json
import requests
import io
import numpy as np
from PIL import Image

API_URL = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000/broker"

def process_image_with_numpy(img_bytes, operation, params):
    try:
        # Načtení do NumPy
        img = Image.open(io.BytesIO(img_bytes))
        
        # Konverze do RGB, aby to fungovalo i u např. PNG s průhledností (RGBA)
        if img.mode != 'RGB':
            img = img.convert('RGB')
            
        img_array = np.array(img)
        
        # 1. Negativ
        if operation == "negative":
            new_array = 255 - img_array
            
        # 2. Zrcadlo
        elif operation == "mirror":
            new_array = img_array[:, ::-1, :]
            
        # 3. Ořez
        elif operation == "crop":
            if not params:
                raise ValueError("Chybí parametry 'params' pro ořez (crop)")
            top = params.get('top', 0)
            bottom = params.get('bottom', 0)
            left = params.get('left', 0)
            right = params.get('right', 0)
            
            h, w, _ = img_array.shape
            
            # Kontrola dimenzí
            if top + bottom >= h or left + right >= w:
                raise ValueError(f"Ořez přesahuje dimenze obrázku (š:{w}, v:{h})")
                
            bottom_slice = -bottom if bottom > 0 else None
            right_slice = -right if right > 0 else None
                
            new_array = img_array[top:bottom_slice, left:right_slice, :]
            
        # 4. Zesvětlení
        elif operation == "brighten":
            value = params.get('value', 50) if params else 50
            # Převod na int16 pro prevenci přetečení (overflow)
            temp_array = img_array.astype(np.int16) + value
            # Oříznutí a návrat na uint8
            new_array = np.clip(temp_array, 0, 255).astype(np.uint8)
            
        # 5. Grayscale (vážený průměr)
        elif operation == "grayscale":
            # R*0.299 + G*0.587 + B*0.114
            gray_array = np.dot(img_array[..., :3], [0.299, 0.587, 0.114])
            # Musíme to zpět převést na 3D matici, aby to bylo kompatibilní s RGB ukládáním
            gray_array_3d = np.stack((gray_array,) * 3, axis=-1)
            new_array = gray_array_3d.astype(np.uint8)
            
        # Neznámá operace
        else:
            raise ValueError(f"Neznámá operace: {operation}")

        # Zpět na byty
        new_img = Image.fromarray(new_array)
        out_io = io.BytesIO()
        new_img.save(out_io, format="PNG")
        return out_io.getvalue(), None
        
    except Exception as e:
        return None, str(e)

async def worker():
    print("[Worker] Připojuji se k brokeru a čekám na úkoly (image.jobs)...")
    try:
        async with websockets.connect(WS_URL) as ws:
            # Subscribe
            await ws.send(json.dumps({"action": "subscribe", "topic": "image.jobs"}))
            
            while True:
                response = await ws.recv()
                data = json.loads(response)
                
                if data.get("action") == "deliver":
                    job = data["payload"]
                    file_id = job["file_id"]
                    operation = job["operation"]
                    print(f"\n[Worker] Přijat úkol pro soubor: {file_id} | Operace: {operation}")
                    
                    # 1. Stažení souboru (REST GET)
                    dl_url = f"{API_URL}/files/{file_id}?user_id={job['user_id']}"
                    headers = {"x-internal-source": "true"}
                    resp = requests.get(dl_url, headers=headers)
                    
                    if resp.status_code == 200:
                        img_bytes = resp.content
                        print(f"[Worker] Soubor stažen. Začínám procesing...")
                        
                        # 2. Zpracování v numpy
                        processed_bytes, err = process_image_with_numpy(img_bytes, operation, job.get("params"))
                        
                        if not err:
                            # 3. Upload nového souboru (REST POST)
                            new_filename = f"{operation}_{job['original_filename']}"
                            files = {"file": (new_filename, processed_bytes, "image/png")}
                            data_form = {"user_id": job["user_id"], "bucket_id": job["bucket_id"]}
                            
                            up_resp = requests.post(f"{API_URL}/files/upload", headers=headers, files=files, data=data_form)
                            
                            if up_resp.status_code in [200, 202]:
                                new_id = up_resp.json().get("id")
                                status = "success"
                                msg = f"Uloženo jako nové ID: {new_id}"
                            else:
                                status = "upload_failed"
                                msg = up_resp.text
                        else:
                            status = "processing_failed"
                            msg = err
                    else:
                        status = "download_failed"
                        msg = f"HTTP {resp.status_code}"

                    print(f"[Worker] Výsledek: {status} ({msg})")
                    
                    # 4. Potvrzení o přečtení
                    await ws.send(json.dumps({"action": "ack", "message_id": data["message_id"]}))
                    
                    # 5. Odeslání výsledku do image.done
                    done_payload = {
                        "original_file_id": file_id,
                        "operation": operation,
                        "status": status,
                        "detail": msg
                    }
                    await ws.send(json.dumps({"action": "publish", "topic": "image.done", "payload": done_payload}))

    except Exception as e:
        print(f"[Worker Error] {e}")

if __name__ == "__main__":
    # Event loop pro nekonečný asynchronní běh
    asyncio.run(worker())