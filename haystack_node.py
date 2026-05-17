import os
import asyncio
import websockets
import json
import msgpack
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, StreamingResponse
import io

app = FastAPI(title="Haystack Storage Node")

# --- KONFIGURACE ---
MAX_VOLUME_SIZE = 100 * 1024 * 1024  # 100 MB
WS_URL = "ws://127.0.0.1:8000/broker"

# Globální stav pro sledování aktuálního svazku
current_volume_id = 1

def get_volume_path(volume_id: int):
    return f"volume_{volume_id}.dat"

def get_current_volume_path():
    return get_volume_path(current_volume_id)

def rotate_volume_if_needed(data_size: int):
    global current_volume_id
    path = get_current_volume_path()
    if os.path.exists(path) and os.path.getsize(path) + data_size > MAX_VOLUME_SIZE:
        current_volume_id += 1
        print(f"[*] Rotace svazku na ID: {current_volume_id}")

@app.get("/volume/{volume_id}/{offset}/{size}")
async def read_needle(volume_id: int, offset: int, size: int):
    path = get_volume_path(volume_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Svazek nenalezen")
    
    try:
        # Synchronní čtení
        with open(path, "rb") as f:
            f.seek(offset)
            data = f.read(size)
            
        if len(data) != size:
            raise HTTPException(status_code=500, detail="Chyba při čtení dat (neočekávaná velikost)")
            
        return Response(content=data, media_type="image/jpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def storage_worker():
    print("[Haystack] Připojuji se k brokeru...")
    while True:
        try:
            async with websockets.connect(WS_URL) as ws:
                # Odebíráme téma storage.write
                subscribe_msg = {"action": "subscribe", "topic": "storage.write"}
                await ws.send(msgpack.packb(subscribe_msg))
                print("[Haystack] Odebírám storage.write")

                while True:
                    raw = await ws.recv()
                    data = msgpack.unpackb(raw)
                    
                    if data.get("action") == "deliver" and data.get("topic") == "storage.write":
                        payload = data["payload"]
                        object_id = payload["object_id"]
                        binary_data = payload["data"]
                        
                        # Zápis dat (Append-only)
                        rotate_volume_if_needed(len(binary_data))
                        path = get_current_volume_path()
                        
                        with open(path, "ab+") as f:
                            offset = f.tell()
                            f.write(binary_data)
                            size = len(binary_data)
                        
                        print(f"[Haystack] Zapsáno: {object_id} -> Vol:{current_volume_id}, Off:{offset}, Size:{size}")
                        
                        # Odeslání ACK
                        ack_payload = {
                            "object_id": object_id,
                            "volume_id": current_volume_id,
                            "offset": offset,
                            "size": size
                        }
                        publish_msg = {
                            "action": "publish",
                            "topic": "storage.ack",
                            "payload": ack_payload
                        }
                        await ws.send(msgpack.packb(publish_msg))
                        
                        # Potvrzení brokeru (message_id)
                        broker_ack = {"action": "ack", "message_id": data["message_id"]}
                        await ws.send(msgpack.packb(broker_ack))

        except Exception as e:
            print(f"[Haystack Error] {e}. Zkouším znovu za 5s...")
            await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    # Zjistíme nejnovější svazek při startu
    global current_volume_id
    v_id = 1
    while os.path.exists(get_volume_path(v_id)):
        v_id += 1
    current_volume_id = max(1, v_id - 1)
    
    # Pokud poslední svazek existuje a je už plný, skočíme na nový
    if os.path.exists(get_volume_path(current_volume_id)):
        if os.path.getsize(get_volume_path(current_volume_id)) >= MAX_VOLUME_SIZE:
            current_volume_id += 1
            
    print(f"[*] Startuji na svazku ID: {current_volume_id}")
    asyncio.create_task(storage_worker())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
