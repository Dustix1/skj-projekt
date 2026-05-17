import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_pub_sub_logic():
    with client.websocket_connect("/broker") as ws_sub, \
         client.websocket_connect("/broker") as ws_pub:
        
        ws_sub.send_json({"action": "subscribe", "topic": "test_topic"})
        ws_pub.send_json({"action": "publish", "topic": "test_topic", "payload": {"data": 123}})
        
        resp = ws_sub.receive_json()
        assert resp["action"] == "deliver"
        assert resp["payload"]["data"] == 123
        
        ws_sub.send_json({"action": "ack", "message_id": resp["message_id"]})