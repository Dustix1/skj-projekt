# Report o využití AI nástrojů - Cvičení 02 (Perzistence a validace)

## Použité nástroje
* Ke splnění úkolů z tohoto cvičení byl využit AI asistent **Gemini** (verze 3.1 Pro).

## Příklady promptů
1. *"čau pookie mám další zadání pro tebe. tady je kód z minula: [VLOŽEN KÓD]"* a nahrání PDF souboru `SKJ_2025S_GAU01_cloud_02_s3_perzistence_a_validace_dat.pdf`.
Tento prompt sloužil k pochopení nového zadání AI asistentem a k aplikování požadavků na existující backend.

## Co AI vygenerovala správně
* AI správně pochopila požadavek na nahrazení "raw slovníků" a definovala Pydantic modely dědící z `BaseModel` (`FileUploadResponse`, `FileItemResponse`, `MessageResponse`).
* Implementovala tyto modely jako návratové typy přímo do dekorátorů endpointů pomocí argumentu `response_model=...`.
* Korektně využila vlastnost `model_config = {"from_attributes": True}`. Tím umožnila FastAPI přímo vracet SQLAlchemy objekty z databáze (např. v endpointu `GET /files` vrací `db.query(...).all()`), aniž by bylo nutné manuálně mapovat data přes for cykly. Pydantic si je nyní parsuje sám.

## Co bylo nutné opravit a jaké chyby AI udělala
* **Chyby AI:** Zpočátku se AI potýkala s tím, jak validovat vstupní `multipart/form-data` requesty pomocí Pydantic modelů. FastAPI sice perfektně integruje Pydantic pro JSON těla requestů, ale použití Pydanticu pro formulářová data (`UploadFile` + string parametry) je komplikovanější. AI proto zvolila kompromis a Pydantic nasadila primárně na návratové hodnoty (`response_model`), zatímco vstupy si ponechaly validaci přes nativní FastAPI moduly `Form(...)` a `File(...)`.
* **Nutné opravy:** Model bylo potřeba lehce přizpůsobit tak, aby dědil vlastnosti (DRY princip) – proto `FileItemResponse` dědí z `FileUploadResponse` a pouze přidává pole `created_at`.