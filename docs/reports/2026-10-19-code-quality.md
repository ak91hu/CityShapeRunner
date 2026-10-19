# Kódminőségi felülvizsgálat és dokumentációrendezés — 2026-10-19

A felülvizsgálat az API-határra, a generálás életciklusára, a kliens
válaszkezelésére, a routing-cache-re, a skillbetöltésre, a csomagolásra és a
dokumentáció használóira összpontosított. Feltételezett környezet: a jelenlegi
Northflank/Docker szolgáltatás, egymást átfedő generálásokkal; illetve helyi
fejlesztés és szabványos Python-csomagtelepítés. Nem teljes biztonsági vagy
elosztott terheléses audit.

## Igazolt hibák és javításuk

### 1. Megszakítás után tovább dolgozó generálás — javítva

- **Működés:** a stream külön szálon indította a generálást, blokkoló sorból
  továbbította az üzeneteket.
- **Hiba:** a kapcsolat bontása nem adott megszakítási jelet a munkafolyamatnak;
  további szolgáltatói hívások indulhattak egy már nem figyelt kéréshez.
- **Javítás:** aszinkron üzenetsor és kérésenkénti megszakítási hatókör. A következő
  munkalépés, routinghívás, LLM-keretellenőrzés vagy keresési határpont megáll.
  A szokásos szolgáltatói hibakezelés nem nyeli el a megszakítást.
- **Elmaradás következménye:** felesleges munka és API-kvóta, tovább élő szerveroldali
  munkaszál. Regresszió: bontott stream után nem indul új Directions-kísérlet;
  a megszakítás nem szivárog át a következő munkafolyamatba.

Érintett helyek: `api/routes.py`, `workflow_runtime.py`, a meglévő orchestrator
erőforrás-felszabadítása. A már elküldött HTTP-kérés befejeződhet; ez együttműködő
megszakítás, nem külső folyamat kényszerített leállítása.

### 2. Sérült stream hálózati hibaként jelent meg — javítva

- **Működés:** a kliens soronként JSON-t olvasott, hiba után csak a reader-zárat
  engedte el.
- **Hiba:** hibás JSON vagy primitív üzenet hálózati hibává alakult; az olvasás
  lezárása nélkül további adat érkezhetett. A streamelt szolgáltatói hibából a
  kérésazonosító és a Retry-After fejléc is elveszett.
- **Javítás:** külön válaszformátum-hiba, üzenet-/eredményalak-ellenőrzés,
  `reader.cancel()` és megőrzött diagnosztikai fejlécek. A takarítás hibája nem
  írja felül az eredeti szolgáltatói hibát.
- **Elmaradás következménye:** félrevezető visszajelzés, háttérben folytatódó
  letöltés és nehezebb hibakeresés.

Érintett hely: `frontend/src/api.js`. A regressziók a byte-onként érkező UTF-8-at,
az újsor nélküli záróüzenetet, a hibás JSON-t, a primitív eredményt, a hiányzó
eredményt és a takarítás közbeni hibát is ellenőrzik.

### 3. Eltérő routingkérések azonos cache-kulcsot kaptak — javítva

- **Működés:** a cache hét tizedesre kerekítette a koordinátákat, háromra az
  indulási irányt, miközben a szolgáltatónak a teljes értékeket küldte.
- **Hiba:** például `47.5` és `47.50000001`, illetve `10` és `10.0001` ugyanabba
  a cache-bejegyzésbe ütközhetett.
- **Javítás:** a kulcs megőrzi a szolgáltatói bemenet teljes pontosságát. Az
  azonos bemenet ismételt kérése továbbra is cache-találat.
- **Elmaradás következménye:** egy korábbi, eltérő kérés útvonala helyettesítheti
  az aktuális szolgáltatói választ.

Érintett hely: `tools/ors_client.py`. Két regressziós eset külön ellenőrzi a
koordináta- és az irányeltérést, valamint az azonos kérés újrahasználatát.

### 4. A telepíthető wheel kihagyta a runtime-skilleket — javítva

- **Működés:** a loader a forrásfa `docs/` mappájában keresett, a wheel viszont
  nem csomagolta be a skill-Markdownokat. Az első elkészített wheelben nulla
  ilyen erőforrás volt.
- **Javítás:** a hét canonical skill forrása `docs/skills/`; a wheel ezeket
  telepítési adatként viszi tovább. A loader forrásfa nélkül a telepítési prefix
  `share/paceasso/skills/` könyvtárát használja. A Docker build másolási útvonalai
  és a csomag README-hivatkozása is frissültek.
- **Elmaradás következménye:** a telepített alkalmazás csendben elveszítheti az
  agentek kiegészítő utasításait.

A regresszió forráscheckout nélkül is betölti a hét skillt. A hét skillfájl és
nyolc agent teljes összeállított promptja az átrendezés előttivel byte-azonos.

## A dokumentáció rendezése

44 dokumentum került tematikus helyre. A központi bejárat a [dokumentációs
index](../index.md). A fizikai csoportok: útmutatók, architektúra, referencia,
fejlesztés, üzemeltetés, design, kutatás, jelentések és runtime-skillek.

A gyökérben a `README.md` és a fejlesztőagentek `AGENTS.md` belépőpontja marad.
A négy `.agents/skills/*/SKILL.md` és a GitHub PR-sablon a toolok által elvárt
helyen marad. Minden további fenntartott Markdown a `docs/` megfelelő
almappájába tartozik; generált bizonyíték a figyelmen kívül hagyott
`test-results/` mappába kerül.

Az áthelyezés érintette a relatív linkeket, HTML-képutakat, MkDocs-navigációt,
a riportkészítőt, a skillbetöltőt, a tesztek dokumentumolvasását, a Python
csomagmetaadatot és a Dockerfile-t is. A 39 korábban publikálható MkDocs-oldal
régi URL-jéhez build közben átirányítás készül, query és fragment megtartásával.
A GitHub forrásfájlokhoz vezető URL-ek követik az új könyvtárszerkezetet.

Az új `scripts/check_documentation.py` a könyvtári rendet és a helyi fájllinkeket
ellenőrzi; a CI dokumentációs kapuja is futtatja. A buildhook megakadályozza,
hogy egy átirányítás meglévő oldalt felülírjon vagy a buildkönyvtáron kívülre
írjon. Az ismét szétszórt Markdown és a hibás link regressziós tesztet buktat.

## Ellenőrzés és mérési korlátok

- Azonos bemenetű pontossági audit: 145 sablon, 580 geometriai pár, 1160
  metrika-összehasonlítás; legnagyobb eltérés **0,0**, minden eredmény bitazonos.
- A minőségi küszöbök, validáció, export, alapgeometria, routingbiztonság és
  sablondefiníciók ellenőrzött kilenc forrásfájlja változatlan.
- A hét runtime-skill és nyolc teljes agentprompt byte-azonossága külön
  SHA-256 összehasonlítással igazolt.
- 21 frontend-egységteszt és a termelési frontendbuild sikeres; 18
  Chromium- és 27 Firefox/WebKit-funkcionális eset sikeres.
- Az új teljes backendfutás **887/887 teszttel sikeres**. Ruff, mypy,
  dokumentációs linkellenőrzés és a szigorú MkDocs-build szintén sikeres.
- A wheel külön Python-környezetbe telepítve is betöltötte mind a hét skillt;
  a nyolc telepített agentprompt is bitazonos. A deklarált függőségeket a
  fejlesztői környezetből tettük elérhetővé, az alkalmazás és erőforrásai a
  wheelből származtak.
- Két régi MkDocs-URL böngészős ellenőrzése igazolta az új oldalra jutást,
  a query és a fragment megőrzését; a build mind a 39 céloldal létezését ellenőrzi.
- A backend, dokumentáció, csomagolás és statikus ellenőrzések végső eredményei
  a `test-results/code-quality-2026-10-19/` bizonyítékcsomagban szerepelnek.
  A kezdeti hibás körök is megmaradnak.

A kezdeti párhuzamos teljes futás Windows memóriafoglalási hibákat okozott;
az érintett köröket elkülönítve ismételtük. Egy tesztben maradt régi Balaton-
dokumentumútvonalat is javítottunk. Az első izolálás nélküli wheel-buildből
hiányzott a buildbackend; a szabványos izolált buildet használjuk.

Nem történt élő ORS-generálás, emberi felismerhetőségi vagy elosztott terheléses
mérés. A numerikus azonosság nem bizonyítja, hogy új élő keresések ugyanazt az
útvonalat adják. Docker Engine nincs ebben a környezetben; a konténer teljes
buildje a meglévő CI-kapu feladata.
