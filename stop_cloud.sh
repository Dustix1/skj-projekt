#!/bin/bash

echo "[*] Vypínám Haystack Cloud Architekturu..."

# 1. Metoda přes PID soubor (pokud existuje)
if [ -f .cloud.pids ]; then
    while read pid; do
        echo "Ukončuji proces $pid..."
        kill $pid 2>/dev/null
    done < .cloud.pids
    rm .cloud.pids
fi

# 2. Pojistka přes pkill (podle jména skriptu)
pkill -f "python3 main.py"
pkill -f "python3 haystack_node.py"
pkill -f "python3 worker.py"

echo "[+] Všechny služby byly ukončeny."
