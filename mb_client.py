import asyncio
import websockets
import json
import msgpack
import sys

async def run_client(mode, topic, use_mp):
    uri = "ws://127.0.0.1:8000/broker"
    async with websockets.connect(uri) as ws:
        if mode == "sub":
            msg = {"action": "subscribe", "topic": topic}
            await ws.send(msgpack.packb(msg) if use_mp else json.dumps(msg))
            print(f"[*] Odebírám {topic}...")
            while True:
                raw = await ws.recv()
                data = msgpack.unpackb(raw) if use_mp else json.loads(raw)
                print(f"[+] Přijato: {data}")
                if data.get("action") == "deliver":
                    ack = {"action": "ack", "message_id": data["message_id"]}
                    await ws.send(msgpack.packb(ack) if use_mp else json.dumps(ack))
        else:
            payload = {"temp": 22.5, "status": "ok"}
            msg = {"action": "publish", "topic": topic, "payload": payload}
            await ws.send(msgpack.packb(msg) if use_mp else json.dumps(msg))
            print(f"[!] Publikováno do {topic}")

if __name__ == "__main__":
    m = sys.argv[1] if len(sys.argv) > 1 else "sub"
    t = sys.argv[2] if len(sys.argv) > 2 else "sensors"
    mp = "--msgpack" in sys.argv
    asyncio.run(run_client(m, t, mp))