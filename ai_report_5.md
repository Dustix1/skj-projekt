# Report o využití AI - Asynchronní zpracování dat (Image Processing)

## Způsob využití AI v projektu
* **Event-Driven Architektura:** AI bylo využito pro návrh asynchronního propojení S3 Gateway s Workerem přes Message Broker (zpracování JSON zpráv, odesílání úloh bez blokování hlavního vlákna).
* **Práce s NumPy a optimalizace:** LLM posloužilo ke generování efektivních vektorizovaných operací nad maticemi obrazu. Tím se předešlo použití neefektivních for-cyklů. Vygenerovaný kód obsahuje jednorádkové operace (např. `img_array[:, ::-1, :]` pro zrcadlení) a řeší technické detaily typu saturace barev přes `np.clip`.
* **Testování a debugging:** AI vygenerovalo výchozí strukturu integračního skriptu `test_worker.py`, který kombinuje odesílání REST požadavků (`httpx`) a asynchronní WebSocket pro příjem notifikací o dokončení. Následně bylo AI využito k debuggování chyby `404 Not Found`, což vedlo k opravě formátu UUID při volání API.

## Použité prompty (Průběh vývoje)
Během řešení úkolu probíhala s AI následující interakce:

1. *"okay mám další úkol momentálně projekt vypadá takhle (zadání pošlu v další zprávě)"* + předložení aktuálních zdrojových kódů.
2. Vložení zadání: *"Asynchronní zpracování dat (toho času obrazu).pdf"*.
3. *"napiš mi celý main"* – žádost o sjednocení kódu Gatewaye s novým `/process` endpointem.
4. *"okay teď co"* – dotaz na další krok v architektuře (následovalo vytvoření testovacího skriptu).
5. Odeslání chybového výpisu: *"Chyba při uploadu: {"detail":"Not Found"}"* – využití AI k analýze logu a detekci problému s předáváním názvu bucketu místo jeho UUID.
6. Odeslání finálního logu potvrzujícího úspěšné zpracování 10/10 úloh.
7. *"zkontroluj zda jsi opravdu udělal všechno co je v zadání"* – ověření podmínek zadání proti vygenerovanému kódu.
8. *"dej do toho AI reportu i moje prompty"* – požadavek na zmapování historie komunikace.