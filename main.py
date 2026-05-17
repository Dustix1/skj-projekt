import os
import uuid
import aiofiles
import json
import msgpack
import asyncio
import websockets
import httpx
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException, Header, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean, ForeignKey, LargeBinary
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from pydantic import BaseModel, Field

# --- PYDANTIC MODELY (S3 & Billing) ---
class BucketCreate(BaseModel):
    name: str = Field(..., title="Název bucketu")

class BucketResponse(BaseModel):
    id: str
    name: str
    created_at: datetime
    model_config = {"from_attributes": True}

class BillingResponse(BaseModel):
    current_storage_bytes: int
    ingress_bytes: int
    egress_bytes: int
    internal_transfer_bytes: int
    count_write_requests: int
    count_read_requests: int
    model_config = {"from_attributes": True}

class FileUploadResponse(BaseModel):
    id: str
    filename: str
    size: int
    bucket_id: str
    status: str
    volume_id: Optional[int] = None
    offset: Optional[int] = None
    model_config = {"from_attributes": True}

class FileItemResponse(FileUploadResponse):
    created_at: datetime
    is_deleted: bool

class MessageResponse(BaseModel):
    message: str

# NOVÝ MODEL PRO WORKERA
class ImageProcessRequest(BaseModel):
    operation: str
    params: Optional[dict] = None

# --- NASTAVENÍ DATABÁZE ---
STORAGE_DIR = "storage"
os.makedirs(STORAGE_DIR, exist_ok=True)

SQLALCHEMY_DATABASE_URL = "sqlite:///./storage.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- SQLALCHEMY MODELY ---
class Bucket(Base):
    __tablename__ = "buckets"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    current_storage_bytes = Column(Integer, default=0)
    ingress_bytes = Column(Integer, default=0)
    egress_bytes = Column(Integer, default=0)
    internal_transfer_bytes = Column(Integer, default=0)
    count_write_requests = Column(Integer, default=0)
    count_read_requests = Column(Integer, default=0)
    files = relationship("FileMetadata", back_populates="bucket")

class FileMetadata(Base):
    __tablename__ = "files"
    id = Column(String, primary_key=True, index=True)
    bucket_id = Column(String, ForeignKey("buckets.id"))
    user_id = Column(String, index=True)
    filename = Column(String)
    path = Column(String)
    size = Column(Integer)
    volume_id = Column(Integer, nullable=True)
    offset = Column(Integer, nullable=True)
    status = Column(String, default="ready") # "uploading", "ready"
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_deleted = Column(Boolean, default=False)
    bucket = relationship("Bucket", back_populates="files")

class QueuedMessage(Base):
    __tablename__ = "queued_messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    topic = Column(String, index=True)
    payload = Column(LargeBinary)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_delivered = Column(Boolean, default=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- CONNECTION MANAGER (Pub/Sub) ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, set[WebSocket]] = {}

    async def subscribe(self, websocket: WebSocket, topic: str):
        if topic not in self.active_connections:
            self.active_connections[topic] = set()
        self.active_connections[topic].add(websocket)

    def unsubscribe(self, websocket: WebSocket, topic: str):
        if topic in self.active_connections:
            self.active_connections[topic].discard(websocket)
            if not self.active_connections[topic]:
                del self.active_connections[topic]

    async def broadcast(self, message_dict: dict, topic: str, is_msgpack: bool):
        if topic in self.active_connections:
            for connection in list(self.active_connections[topic]):
                try:
                    if is_msgpack:
                        await connection.send_bytes(msgpack.packb(message_dict))
                    else:
                        await connection.send_json(message_dict)
                except Exception:
                    self.unsubscribe(connection, topic)

manager = ConnectionManager()

# --- POMOCNÉ FUNKCE PRO DB (v Threadpoolu) ---
def db_save_message(topic: str, payload: bytes):
    with SessionLocal() as db:
        msg = QueuedMessage(topic=topic, payload=payload)
        db.add(msg)
        db.commit()
        db.refresh(msg)
        return msg.id

def db_ack_message(msg_id: int):
    with SessionLocal() as db:
        msg = db.query(QueuedMessage).filter(QueuedMessage.id == msg_id).first()
        if msg:
            msg.is_delivered = True
            db.commit()

def db_get_undelivered(topic: str):
    with SessionLocal() as db:
        msgs = db.query(QueuedMessage).filter(QueuedMessage.topic == topic, QueuedMessage.is_delivered == False).all()
        return [{"id": m.id, "payload": m.payload} for m in msgs]

app = FastAPI(title="Cloud Object Storage & Message Broker")

# --- AUTO-CREATE TABLES ---
Base.metadata.create_all(bind=engine)

# --- BACKGROUND WORKER PRO STORAGE ACK ---
async def haystack_ack_worker():
    uri = "ws://127.0.0.1:8000/broker"
    while True:
        try:
            async with websockets.connect(uri) as ws:
                subscribe_msg = {"action": "subscribe", "topic": "storage.ack"}
                await ws.send(msgpack.packb(subscribe_msg))
                print("[Gateway] Ack worker připojen k brokeru")
                
                while True:
                    raw = await ws.recv()
                    data = msgpack.unpackb(raw)
                    
                    if data.get("action") == "deliver" and data.get("topic") == "storage.ack":
                        payload = data["payload"]
                        object_id = payload["object_id"]
                        volume_id = payload["volume_id"]
                        offset = payload["offset"]
                        size = payload["size"]
                        
                        with SessionLocal() as db:
                            f = db.query(FileMetadata).filter(FileMetadata.id == object_id).first()
                            if f:
                                f.volume_id = volume_id
                                f.offset = offset
                                f.status = "ready"
                                # Billing se strhne až teď
                                b = f.bucket
                                b.ingress_bytes += size
                                db.commit()
                                print(f"[Gateway] Potvrzen zápis pro {object_id} -> Vol:{volume_id}")
                        
                        # Ack brokeru
                        ack = {"action": "ack", "message_id": data["message_id"]}
                        await ws.send(msgpack.packb(ack))
        except Exception as e:
            print(f"[Gateway Ack Worker Error] {e}")
            await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(haystack_ack_worker())

# --- WEBSOCKET BROKER ENDPOINT ---
@app.websocket("/broker")
async def broker_endpoint(websocket: WebSocket):
    await websocket.accept()
    subscribed_topics = set()
    try:
        while True:
            received = await websocket.receive()
            
            if received.get("type") == "websocket.disconnect":
                raise WebSocketDisconnect()
            
            if "bytes" in received and received["bytes"]:
                data = msgpack.unpackb(received["bytes"])
                is_msgpack = True
            elif "text" in received and received["text"]:
                data = json.loads(received["text"])
                is_msgpack = False
            else:
                continue

            action = data.get("action")
            topic = data.get("topic")

            if action == "publish":
                payload = data.get("payload")
                payload_raw = msgpack.packb(payload)
                msg_id = await run_in_threadpool(db_save_message, topic, payload_raw)
                
                deliver_msg = {"action": "deliver", "topic": topic, "message_id": msg_id, "payload": payload}
                await manager.broadcast(deliver_msg, topic, is_msgpack)

            elif action == "subscribe":
                await manager.subscribe(websocket, topic)
                subscribed_topics.add(topic)
                
                undelivered = await run_in_threadpool(db_get_undelivered, topic)
                for m in undelivered:
                    hist_msg = {"action": "deliver", "topic": topic, "message_id": m["id"], "payload": msgpack.unpackb(m["payload"])}
                    
                    try:
                        if is_msgpack: 
                            await websocket.send_bytes(msgpack.packb(hist_msg))
                        else: 
                            await websocket.send_json(hist_msg)
                    except Exception:
                        break

            elif action == "ack":
                await run_in_threadpool(db_ack_message, data.get("message_id"))

    except WebSocketDisconnect:
        for t in subscribed_topics: 
            manager.unsubscribe(websocket, t)

# --- S3 ENDPOINTY ---
@app.post("/buckets/", response_model=BucketResponse, tags=["Buckets"])
async def create_bucket(bucket_in: BucketCreate, db: Session = Depends(get_db)):
    if db.query(Bucket).filter(Bucket.name == bucket_in.name).first():
        raise HTTPException(status_code=400, detail="Bucket již existuje")
    new_b = Bucket(name=bucket_in.name); db.add(new_b); db.commit(); db.refresh(new_b)
    return new_b

@app.get("/buckets/{bucket_id}/billing/", response_model=BillingResponse, tags=["Buckets"])
async def get_billing(bucket_id: str, db: Session = Depends(get_db)):
    b = db.query(Bucket).filter(Bucket.id == bucket_id).first()
    if not b: raise HTTPException(status_code=404)
    return b

@app.post("/files/upload", response_model=FileUploadResponse, status_code=202, tags=["Files"])
async def upload(file: UploadFile = File(...), user_id: str = Form(...), bucket_id: str = Form(...), x_internal_source: Optional[str] = Header(None), db: Session = Depends(get_db)):
    bucket = db.query(Bucket).filter(Bucket.id == bucket_id).first()
    if not bucket: raise HTTPException(status_code=404)
    
    f_id = str(uuid.uuid4())
    content = await file.read()
    size = len(content)
    
    # 1. Uložíme metadata se statusem "uploading"
    db_f = FileMetadata(id=f_id, bucket_id=bucket_id, user_id=user_id, filename=file.filename, size=size, status="uploading")
    db.add(db_f)
    bucket.count_write_requests += 1
    bucket.current_storage_bytes += size
    db.commit()
    db.refresh(db_f)
    
    # 2. Odešleme data Haystacku přes Broker
    publish_payload = {
        "object_id": f_id,
        "data": content
    }
    msg_data = {
        "action": "deliver", 
        "topic": "storage.write", 
        "message_id": 0, # Dočasné ID pro broadcast
        "payload": publish_payload
    }
    
    # Publikujeme přímo přes manager.broadcast pro rychlost
    await manager.broadcast(msg_data, "storage.write", is_msgpack=True)
    
    # Také uložíme do DB fronty pro odolnost (durable queue)
    await run_in_threadpool(db_save_message, "storage.write", msgpack.packb(publish_payload))
    
    return db_f

@app.get("/files/{id}", tags=["Files"])
async def download(id: str, user_id: str, x_internal_source: Optional[str] = Header(None), db: Session = Depends(get_db)):
    f = db.query(FileMetadata).filter(FileMetadata.id == id, FileMetadata.is_deleted == False).first()
    if not f or f.user_id != user_id: raise HTTPException(status_code=404)
    
    if f.status != "ready":
        raise HTTPException(status_code=202, detail="Soubor se stále nahrává")

    bucket = f.bucket; bucket.count_read_requests += 1
    if x_internal_source == "true": bucket.internal_transfer_bytes += f.size
    else: bucket.egress_bytes += f.size
    db.commit()
    
    # Proxy požadavek na Haystack Node
    haystack_url = f"http://127.0.0.1:8001/volume/{f.volume_id}/{f.offset}/{f.size}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(haystack_url)
            if resp.status_code == 200:
                return Response(content=resp.content, media_type="image/jpeg", headers={"Content-Disposition": f"attachment; filename={f.filename}"})
            else:
                raise HTTPException(status_code=500, detail="Haystack Node error")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Proxy error: {str(e)}")

@app.delete("/files/{id}", response_model=MessageResponse, tags=["Files"])
async def soft_delete(id: str, user_id: str, db: Session = Depends(get_db)):
    f = db.query(FileMetadata).filter(FileMetadata.id == id).first()
    if not f or f.user_id != user_id: raise HTTPException(status_code=404)
    f.is_deleted = True; f.bucket.count_write_requests += 1; db.commit()
    return {"message": f"Soubor {id} smazán (Soft Delete)"}

@app.get("/buckets/{bucket_id}/objects/", response_model=List[FileItemResponse], tags=["Buckets"])
async def list_objects(bucket_id: str, db: Session = Depends(get_db)):
    bucket = db.query(Bucket).filter(Bucket.id == bucket_id).first()
    if not bucket: raise HTTPException(status_code=404)
    bucket.count_read_requests += 1; db.commit()
    return db.query(FileMetadata).filter(FileMetadata.bucket_id == bucket_id, FileMetadata.is_deleted == False).all()


@app.get("/internal/volumes/{volume_id}/objects", tags=["Internal"])
async def get_volume_objects(volume_id: int, db: Session = Depends(get_db)):
    return db.query(FileMetadata).filter(FileMetadata.volume_id == volume_id, FileMetadata.is_deleted == False).all()

@app.patch("/internal/files/{id}/location", tags=["Internal"])
async def update_file_location(id: str, volume_id: int = Form(...), offset: int = Form(...), db: Session = Depends(get_db)):
    f = db.query(FileMetadata).filter(FileMetadata.id == id).first()
    if not f: raise HTTPException(status_code=404)
    f.volume_id = volume_id
    f.offset = offset
    db.commit()
    return {"status": "updated"}

# --- IMAGE PROCESSING ENDPOINT ---
@app.post("/buckets/{bucket_id}/objects/{id}/process", tags=["Processing"])
async def process_image(
    bucket_id: str, 
    id: str, 
    process_req: ImageProcessRequest, 
    user_id: str = Header(...),
    db: Session = Depends(get_db)
):
    # 1. Kontrola oprávnění a existence souboru
    db_file = db.query(FileMetadata).filter(FileMetadata.id == id, FileMetadata.bucket_id == bucket_id, FileMetadata.is_deleted == False).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="Soubor nenalezen")
    if db_file.user_id != user_id:
        raise HTTPException(status_code=403, detail="Přístup odepřen")

    # 2. Vytvoření jobu pro Workera
    job_payload = {
        "file_id": id,
        "bucket_id": bucket_id,
        "user_id": user_id,
        "operation": process_req.operation,
        "params": process_req.params,
        "original_filename": db_file.filename
    }

    # Zabalení do MessagePack pro náš Message Broker
    payload_raw = msgpack.packb(job_payload)
    
    # 3. Uložení zprávy do Durable Queue a Broadcast všem připojeným Workerům
    topic = "image.jobs"
    msg_id = await run_in_threadpool(db_save_message, topic, payload_raw)
    
    deliver_msg = {
        "action": "deliver", 
        "topic": topic, 
        "message_id": msg_id, 
        "payload": job_payload
    }
    
    # Odešleme ve formátu JSON (is_msgpack=False), worker.py to tak momentálně čte
    await manager.broadcast(deliver_msg, topic, is_msgpack=False)

    # 4. Asynchronní odpověď klientovi – nečekáme na zpracování!
    return {
        "status": "processing_started", 
        "job_id": msg_id, 
        "operation": process_req.operation
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
