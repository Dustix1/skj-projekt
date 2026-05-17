# Report o využití AI - Vlastní Message Broker (Pub/Sub)

## Jak AI pomohlo s návrhem
* **ConnectionManager:** AI pomohla navrhnout strukturu pro správu WebSocket spojení a dynamické směrování (routing) zpráv. Skvěle vyřešila logiku pro dynamické přepínání mezi `send_json` a `send_bytes` na základě detekce formátu příchozí zprávy.
* **Asynchronní vs Synchronní databáze (Durable Queues):** Jelikož předchozí cvičení stavělo na synchronní SQLAlchemy `Session`, její použití přímo uvnitř asynchronního `while True` cyklu WebSocketu by kompletně zablokovalo Event Loop (a tím i ostatní klienty). AI navrhla elegantní řešení obalením databázových I/O operací do funkce `fastapi.concurrency.run_in_threadpool`. Tím se zamezilo blokování bez nutnosti náročného přepisu celé architektury na `AsyncSession`.
* **Pytest a WebSockety:** AI vygenerovala funkční integrační testy využívající knihovnu `httpx` a kontextové manažery `with client.websocket_connect(...)`. To značně ulehčilo testování směrování zpráv mezi vícero klienty (Subscribery a Publishery) najednou.
