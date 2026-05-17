# Report o využití AI - Facebook Haystack a Event-Driven Architektura

## Způsob využití AI v projektu
* **Architektonická transformace (Facebook Haystack):** AI provedlo transformaci původního souborového úložiště na plnohodnotnou "Haystack" architekturu. To zahrnovalo vytvoření nové mikroslužby `haystack_node.py`, která fyzicky spravuje velké binární svazky (`volume_X.dat`) formou extrémně rychlého "Append-only" zápisu, čímž se eliminuje overhead tradičních souborových systémů (disk seek).
* **Event-Driven a Eventual Consistency:** Původní `main.py` (S3 Gateway) byl AI přepracován tak, aby fungoval plně asynchronně. Zápis do databáze probíhá zprvu pouze do stavu `uploading`. Fyzická data jsou předána Message Brokeru, který je odešle do Haystack Node. S3 Gateway na pozadí poslouchá téma `storage.ack` a teprve po potvrzení z Haystack Node přiřadí souboru finální `volume_id` a `offset` a přepne jej do stavu `ready`. AI také upravilo existující `worker.py` (Image Processing), aby do tohoto asynchronního toku správně zapadl.
* **Správa databáze a kompakce:** AI zajistilo automatickou inicializaci databáze a integraci nových metadat do Pydantic/SQLAlchemy modelů (automatické volání `Base.metadata.create_all`). Dále AI implementovalo skript `compact.py`, který na vyžádání provede defragmentaci objemných svazků (odstraní smazané soubory, přesune "živé" objekty do nového souboru a updatuje offsety přes interní API v S3 Gateway).
* **CI/CD a procesní automatizace:** Pro zjednodušení lokálního vývoje a prezentace AI vygenerovalo `.gitignore` soubor, inicializovalo git repozitář a nastavilo odesílání na GitHub. Pro správu celého cloudu byly vytvořeny bash skripty `start_cloud.sh` a `stop_cloud.sh`.
* **Pokročilé testování a tvorba Live Dema:** AI vytvořilo komplexní vizuální prezentační skript `demo.py`, který barvami v terminálu automaticky krok za krokem demonstruje vytvoření bucketu, odeslání požadavku (s výpisem `curl` příkazů a JSON odpovědí), čekání na ACK, zpracování obrazu přes worker a zpětné stažení z proxy S3 Gateway. Skript navíc asynchronně monitoruje a vypisuje raw komunikaci z Message Brokeru pro jasnou demonstraci nezávislých mikroslužeb.

## Použité prompty (Průběh vývoje)
Během řešení úkolu probíhala s AI následující interakce:

1. *"read the project to understand it and then read this @Projekt_ Facebook Haystack a Event-Driven Architektura.pdf this is the next task that we need to implement..."* + poskytnutí fotky tabule s návrhem.
2. *"why did you delete all the files"* – reakce na nechtěné smazání souborů ze strany AI, po kterém AI okamžitě provedlo obnovu ze svého kontextu.
3. *"test everything and then tell me how you tested it and how i should test it and what to expect or how to know if it worked"* – žádost o plnou verifikaci a instruktáž k testování.
4. *"when i do this curl -X POST -F "file=choese.webp"... it says some dquote idk what that is"* – řešení překlepu v příkazové řádce uživatele.
5. *"okay now i still have to test the image worker no?"* – požadavek na zprovoznění a ověření stávajícího image workera v nové Haystack architektuře.
6. *"so its working through the message broker (the storage node and the worker should work throught the message broker with the s3 gateway)"* – dotaz na potvrzení finální architektury toků dat.
7. *"so now for the whole thing to be started i need to run main.py... but what is compact.py and where is the broker?"* – vyjasnění role jednotlivých komponent (Gateway/Broker vs. Defragmentace).
8. *"can you create a script or something that starts all the things in background terminals or something and then a thing that kills them"* – vytvoření skriptů `start_cloud.sh` a `stop_cloud.sh`.
9. *"create a .gitignore so that i can pull it on my notebook and be able to run it. also upload the start and stop scripts. and push it here [github link]"* – příprava pro migraci na notebook a pushnutí kódu na repozitář.
10. *"create a test script that creates a bucket and uploads choese.webp then shows everything with the uploading and then ready... so i can present it easily"* – vytvoření základu pro finální `demo.py`.
11. *"what nothing was fixed (and i renamed it to demo.py)... ModuleNotFoundError: No module named 'requests'"* – odhalení a řešení problému s virtuálním prostředím Pythonu a spouštěním skriptu správným interpretem z `.venv`.
12. *"also show the commands used and raw responses in the demo"* – požadavek na obohacení dema o přesné zobrazení REST volání.
13. *"dej tam i výpis z message brokeru"* – požadavek na živé sledování interní Message Broker komunikace ve sdíleném terminálu pro efekt prezentace.
14. *"when i pulled the project and tried to start it after creating the venv and installing requirements it throws a lot of errors with sqlalchemy no such table"* – oprava chybějící inicializace struktury databáze (přidáno `Base.metadata.create_all`).
15. *"okay nice a ještě u toho zpracování nejde vidět žádná zpráva z message brokeru"* a *"it does show the image.done theme but only the ones at the start from previous tests"* – oprava chování monitorovacího vlákna v demu, které původně ignorovalo textový JSON od Workera (dekódovalo jen MsgPack).
16. *"okay now it works"* – potvrzení funkčnosti celého systému a prezentačního skriptu.
17. *"vygeneruj ai_report_6.md podívej se na předešlé reporty. dej tam moje prompty atd"* – tento finální prompt k vytvoření reportu.
