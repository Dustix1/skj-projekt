# Report o využití AI nástrojů - Object Storage (S3-like služba)

## Použité nástroje
* Ke splnění této úlohy byl použit AI asistent **Gemini** (verze 3.1 Pro). 

## Příklady promptů
1. *"ahoj puso udělej to s sqllite databází, u downloadu vždycky musíš zadávat usera"* - Hlavní prompt pro návrh architektury, generování endpointů a vynucení autentizace přes `user_id`.
2. *"co mám stáńout do pipuu"* - Prompt pro vygenerování přesného příkazu pro instalaci potřebných závislostí.

## Co AI vygenerovala správně
* Kompletní kostru backendu ve frameworku FastAPI.
* Databázový model pomocí SQLAlchemy pro SQLite (včetně všech metadat jako `id`, `user_id`, `filename`, `path`, `size`, `created_at`).
* Logiku pro asynchronní čtení a zápis souborů po menších částech pomocí knihovny `aiofiles`, což brání zahlcení paměti RAM při nahrávání velkých souborů.
* Správnou logiku pro tvorbu složek uživatelů a zamezení kolizí jmen souborů.

## Co bylo nutné opravit a jaké chyby AI udělala
* **Chyby AI:** Samotný kód vygenerovaný AI fungoval na první pokus. AI ale původně nezmínila, že použití `File(...)` a `Form(...)` v jednom endpointu může být u některých jednodušších HTTP klientů obtížnější na složení requestu (vyžaduje to přesné nastavení `multipart/form-data`). Dále nezmínila, že složka `storage/` se nevytvoří sama, pokud k tomu explicitně nedám příkaz v kódu (což AI sice do kódu naštěstí dopsala přes `os.makedirs`, ale nevysvětlila to).