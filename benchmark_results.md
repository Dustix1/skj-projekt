# Výsledky Benchmarku Message Brokera

## 1. Konfigurace počítače
* **Operační systém:** Linux 6.19.11-arch1-1
* **Procesor:** Neznámý CPU (Počet logických jader: 16)
* **Databáze:** SQLite (Lokální soubor .db)

## 2. Naměřená propustnost
* **Formát JSON:** 123.87 msg/s
* **Formát MessagePack:** 140.88 msg/s

## Zhodnocení
Binární formát MessagePack prokazatelně dosahuje vyšší propustnosti. Komprese dat do binární podoby snižuje velikost posílaných rámců přes síť (WebSockets) a zároveň je rychlejší na serializaci a deserializaci oproti textovému JSONu. V cloudovém nasazení (kde se platí za přenesená data a čas procesoru) se MessagePack pro asynchronní mikroslužby rozhodně vyplatí.
