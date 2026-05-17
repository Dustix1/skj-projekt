#!/bin/bash

# --- KONFIGURACE ---
VENV_PYTHON="./.venv/bin/python3"
LOG_DIR="./logs"

# Vytvoření složky pro logy, pokud neexistuje
mkdir -p $LOG_DIR

echo "[*] Startuji Haystack Cloud Architekturu..."

# 1. Start S3 Gateway + Broker (Port 8000)
echo "[1/3] Startuji S3 Gateway (Broker) na portu 8000..."
$VENV_PYTHON main.py > $LOG_DIR/gateway.log 2>&1 &
GATEWAY_PID=$!

# Čekáme chvíli, než se Broker nastartuje, aby se k němu ostatní mohli připojit
sleep 3

# 2. Start Haystack Node (Port 8001)
echo "[2/3] Startuji Haystack Storage Node na portu 8001..."
$VENV_PYTHON haystack_node.py > $LOG_DIR/haystack.log 2>&1 &
HAYSTACK_PID=$!

# 3. Start Image Worker
echo "[3/3] Startuji Image Processing Worker..."
$VENV_PYTHON worker.py > $LOG_DIR/worker.log 2>&1 &
WORKER_PID=$!

echo "--------------------------------------------------"
echo "[+] Všechny služby běží na pozadí!"
echo "[+] Logy najdeš ve složce: $LOG_DIR"
echo "[+] Pro vypnutí použij: ./stop_cloud.sh"
echo "--------------------------------------------------"

# Uložení PIDů pro stop script (volitelné, pkill je jistější, ale toto je čistší)
echo $GATEWAY_PID > .cloud.pids
echo $HAYSTACK_PID >> .cloud.pids
echo $WORKER_PID >> .cloud.pids
