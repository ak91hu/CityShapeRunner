# Webapp- és dokumentációellenőrzés — 2026. október 26.

Az ellenőrzés alapja a `1130ff2` master-verzió. A javítások ehhez képest helyi
munkapéldányban készültek; ez a beszámoló önmagában nem jelent éles kiadást.

## Megtalált és javított működési hibák

| Helyzet | Korábbi következmény | Javítás |
| --- | --- | --- |
| Alakfelismerési javítás után megváltozik az utcai geometria | A felület a korábbi útvonal minősítését és TCX-fájlját örökölhette | A javítás az `/edit-route` meglévő ellenőrzési és exportálási folyamatát használja. A felület együtt cseréli a metrikákat, ellenőrzéseket, részleteket és fájlokat; gyengébb eredményhez új elfogadás kell |
| Egyenletes körvonalhoz nincs elegendő kiemelkedő sarok | A javító útvonalvezetés egyetlen pontra is összeeshetett | A meglévő görbületőrző mintavételező legfeljebb 12 vezetőpontot készít. A teljes eredeti körvonal marad az összehasonlítás alapja; az egybeeső pontokból álló kérés még a szolgáltató hívása előtt elutasítást kap |
| A felhasználó egy függő szerkesztés vagy javítás közben másik útvonalat választ | A régi válasz felülírhatta az új választást | Közös kérésvezérlő megszakítja az elavult műveletet, és csak az aktuális kérés módosíthat állapotot |
| A felhasználó elindítja az áttekintett kérést | A generálás ismét értelmezte a szöveget, így modellfüggő eltérés keletkezhetett | A frontend a bemutatott értelmezést a meglévő `intent_override` mezőben továbbítja |

A javított útvonal az eredeti galériamegosztási token helyett frisset kap,
ha a galéria konfigurálva van; az opcionális megosztás így megmarad.
Az utcai szolgáltatói geometria követelménye, a minőségi küszöbök, a távolság- és
zártságellenőrzések, valamint a mérési felbontás változatlanok.

## Dokumentáció

Az aktuális útmutatók és referenciaoldalak az alábbiakban tértek el a kódtól:

- hat állandó kezdőötlet helyett hat kevert ötlet jelenik meg a 158 elemű
  katalógusból, külön frissítési lehetőséggel;
- az alapértelmezett keresés 180 korábbi és 90 kreatív elhelyezést enged,
  hét korábbi és legfeljebb két kreatív döntőssel; az éles, korlátozott
  memóriájú profil eltérő kereteit külön kell olvasni;
- a generálás böngészős időkorlátja képes és szöveges kérésnél egyaránt
  240 másodperc; az értelmezésé 20, a szerkesztésé, javításé és mural-tervé 180;
- a YAML alap finomítási kerete nyolc, a YAML nélküli kódbeli tartalékérték hat;
- a fejlesztési OpenCode CLI és a közvetlen API eltérő beállításokat használ;
- a tesztelési útmutatókban a Node egységtesztek, az öt böngészőprofil,
  valamint a dokumentációellenőrző parancsok is szerepelnek.

A korábbi, dátumozott auditok megőrzik saját mérési időpontjuk adatait.
Külső tanulmányok és szolgáltatói modellkatalógusok teljes újraellenőrzése
nem része ennek a helyi kód- és dokumentációauditnak.

## Ellenőrzési eredmények

| Ellenőrzés | Eredmény |
| --- | --- |
| Teljes backend tesztsorozat a végleges kódon | **968 sikeres**, 65,73 s |
| Ruff és mypy | Sikeres; 71 Python-forrásfájl típusellenőrzése |
| `npm run check` | **26 sikeres egységteszt**, sikeres produkciós build |
| Teljes eredményoldali és szerkesztési résztesztsorozat az első javítás után | **84 sikeres** asztali/mobil Chromiumban |
| Főfolyamatok és smoke tesztek | **95 sikeres**, egy mobilos teszt túl korán mért elemgeometriát; a megjelenés bevárását javítottam, majd az esetet mind az öt profilban újraellenőriztem |
| Teljes tervezőoldali és alapalkalmazási résztesztsorozat | **78 sikeres** asztali/mobil Chromiumban |
| Végleges javítások célzott regressziói | **12 sikeres** asztali/mobil Chromiumban, **18 sikeres** Firefoxban, asztali és mobil WebKitben |
| Azonos bemenetű pontozási audit a masterhez képest | **1160 összehasonlítás bitre azonos**, 145 sablon 580 geometriai párján; a védett minőségi és geometriai fájlok változatlanok |
| Dokumentáció | `python scripts/check_documentation.py` és `python -m mkdocs build --strict` |
| Éles oldal, asztali és mobil nézet | A kezdőlap, `/health` és `/interpret` sikeres; hat új ötlet, megőrzött szöveg és fókusz; galériakép betölt; nincs vízszintes túlcsordulás vagy kezeletlen JavaScript-hiba |

A teszteredmények külön szakaszokból származnak, részben átfednek; nem adják ki
a teljes kiadási böngészős tesztsorozatot. A végső célzott esetek az új
GPX/TCX-tartalmat, a friss ellenőrzéseket és megosztási tokent, a késői válaszok
megszakítását, a jóváhagyott értelmezés átadását és a 320 px-es elrendezést is
ellenőrzik. A build jelzi a külön betöltött MapLibre walkthrough-csomag méretét;
ennek csökkentése nem része a javításnak.

A generált naplók, képernyőképek és összehasonlítások az ignorált
`test-results/webapp-audit-2026-10-26/` mappában vannak. Az első smoke futás
eredeti hibája külön naplóban és képernyőképben megmaradt.

## Ellenőrzési határok

Az éles ellenőrzés nem indított új `/generate` hívást és nem tett közzé térképet.
A javítások utáni élő szolgáltatói alakminőség és késleltetés nincs újramérve;
a pontozási audit nem élő útvonalminőségi benchmark. A teljes kiadási CI-kapu,
konténerbuild és éles telepítés nem futott ebben a feladatban.
