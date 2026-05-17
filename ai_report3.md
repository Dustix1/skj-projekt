# Report o využití AI nástrojů - Cvičení 03 (Evoluce DB a Alembic)

## Použité nástroje
* Ke splnění úkolů z tohoto cvičení byl využit AI asistent **Gemini**.

## Příklady promptů
1. *"okay tak máme tady další věc na práci poslal jsem ti zadání a main.py co máme teď"* - Prompt doplněn o PDF se zadáním týkajícím se nástroje Alembic, vytváření Bucketů, soft delete a trackování přenesených dat (billing).

## Co AI vygenerovala správně
* AI perfektně připravila SQLAlchemy modely a propojila tabulku `Bucket` s `FileMetadata` pomocí `ForeignKey` a `relationship`.
* Korektně naimplementovala Pydantic modely (např. `BillingResponse`) tak, aby plně korespondovaly se strukturou FastAPI endpointů.
* Správně implementovala výpočet Ingress a Internal dat pomocí detekce volitelného hlavičkového pole `x_internal_source: Optional[str] = Header(None)`.
* Úspěšně zvládla logiku Soft Delete – operace DELETE z databáze a z disku nemaze fyzicky, ale pouze přepíná flag `is_deleted = True`. Endpoint `GET` a filtrace pak automaticky skrývají tyto "vymazané" soubory. Také správně pochopila, že kapacita se nesmí při Soft Delete odečítat od celkového úložiště.

## Co bylo nutné upravit / jaké chyby AI udělala (a jak jsme je řešili)
* **Chyba AI:** AI zpočátku navrhla pouze konečný výsledný kód. To by znamenalo, že příkaz `alembic revision --autogenerate` by vygeneroval jen jednu jedinou obrovskou migraci.
* **Nutné opravy:** Kód jako takový byl správně, ale abychom dodrželi zadání "vygenerujte první/druhou/třetí migraci", bylo nutné postupovat iterativně. Tedy nejprve z kódu některé atributy (billing, is_deleted) dočasně odstranit (zakomentovat), nechat Alembic vygenerovat první migraci, atributy vrátit, nechat vygenerovat druhou atd. AI mě na tento postup musela v odpovědi sama navést. Dále bylo nutné ručně zajistit úpravy v souboru `alembic/env.py` (`sys.path.append(...)`), protože Alembic zpočátku neviděl do aktuálního kontextu spuštění FastAPI.