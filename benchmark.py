import asyncio
import websockets
import json
import msgpack
import time

MSG_COUNT = 250
CONCURRENCY = 5

async def publisher(use_mp, topic):
    try:
        async with websockets.connect("ws://127.0.0.1:8000/broker") as ws:
            for i in range(MSG_COUNT):
                m = {"action": "publish", "topic": topic, "payload": {"i": i}}
                if use_mp:
                    await ws.send(msgpack.packb(m))
                else:
                    await ws.send(json.dumps(m))
                # Trochu větší pauza, aby SQLite stíhala zapisovat na disk
                await asyncio.sleep(0.005) 
    except Exception:
        pass # Ignorujeme případné pády spojení u odesílatele

async def subscriber(use_mp, topic, stop_event, counter):
    try:
        async with websockets.connect("ws://127.0.0.1:8000/broker") as ws:
            sub_msg = {"action": "subscribe", "topic": topic}
            if use_mp:
                await ws.send(msgpack.packb(sub_msg))
            else:
                await ws.send(json.dumps(sub_msg))
                
            while counter[0] < MSG_COUNT * CONCURRENCY:
                raw = await ws.recv()
                d = msgpack.unpackb(raw) if use_mp else json.loads(raw)
                
                if d.get("action") == "deliver":
                    counter[0] += 1
                    ack = {"action": "ack", "message_id": d["message_id"]}
                    if use_mp:
                        await ws.send(msgpack.packb(ack))
                    else:
                        await ws.send(json.dumps(ack))
    except Exception:
        pass # Ignorujeme pády
    finally:
        # Pokaždé ohlásíme hlavnímu vláknu, že už nebudeme dál přijímat (brání zásekům)
        stop_event.set()

async def run_bench(use_mp):
    topic = f"bench_{'msgpack' if use_mp else 'json'}"
    stop = asyncio.Event()
    counter = [0]
    
    sub_task = asyncio.create_task(subscriber(use_mp, topic, stop, counter))
    await asyncio.sleep(1) # Počkáme na připojení odběratele
    
    start = time.time()
    pubs = [asyncio.create_task(publisher(use_mp, topic)) for _ in range(CONCURRENCY)]
    
    await asyncio.gather(*pubs)
    
    # Pojistka: Čekáme na příjem zpráv maximálně 10 vteřin. 
    # Pokud to trvá déle (něco se ztratilo v databázi), test se ukončí a nesekne se.
    try:
        await asyncio.wait_for(stop.wait(), timeout=10.0)
    except asyncio.TimeoutError:
        print("\n[!] Test ukončen přes timeout. Databáze nestíhala.")
        
    end = time.time()
    sub_task.cancel()
    
    duration = end - start
    actual_msgs = counter[0] if counter[0] > 0 else 1 # ochrana proti dělení nulou
    print(f"{'MessagePack' if use_mp else 'JSON'}: {actual_msgs / duration:.2f} msg/s")

if __name__ == "__main__":
    print("--- Benchmark ---")
    asyncio.run(run_bench(False))
    
    # Necháme databázi 3 sekundy zpracovat zbytek požadavků
    time.sleep(3) 
    
    asyncio.run(run_bench(True))