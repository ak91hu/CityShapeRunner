# Generálási késleltetés — 2026-11-02

## Élő kiinduló mérés

A `dd6d933` éles verzió három egymást követő, valódi `/generate` kérését
mértük Budapesten, 8 km-es futással és `20261102` keresési seed-del.
A teljes idő kliensoldali mérés; az előnézet az első szolgáltató által
utcára illesztett geometria eseménye. Mindegyik eredmény `needs_review`:
összefüggő utcai útvonal, de nem minden alakminőségi kapun ment át.

| Kérés | Teljes idő | Első utcai előnézet | Rajzfázis | AI-hívások |
| --- | ---: | ---: | ---: | --- |
| szív | 92,59 s | 17,68 s | 0,09 s | nincs |
| bal kézzel integető robot | 81,59 s | 52,44 s | 32,76 s | 2 OpenCode |
| nyitott esernyőt tartó robot | 84,88 s | 56,42 s | 36,65 s | 2 Groq, majd 1 OpenCode |

Ez nem modell-összehasonlítás: a két egyedi kérés eltérő rajzot kért.
A Groq-os eset tartalék szolgáltatóra váltott; a progress eseményekből
a váltás oka nem állapítható meg. A teljes várakozás nem csak LLM-idő.
A szívnél a kontúrjavítás három fázisa 16,20, 27,50 és 15,30 másodpercet
vitt el; az utolsó már routing-kérés nélkül. A munkafolyamat túlfutott
a 75 másodperces kereten, mert a már elindult szinkron számítás befejeződik.
A beágyazott fázisidők átfedhetnek, ezért nem összegezhetők egyszerűen.

A Northflank `nf-compute-10` (0,1 vCPU / 256 MB) profilján a mérési időszakban
100%-os CPU- és 90,14%-os memóriahasználati csúcs jelent meg. Ez a CPU-igényes
geometriai utómunka optimalizálását indokolja; önmagában nem bizonyítja,
mekkora gyorsulást adna egy nagyobb csomag.

Bizonyíték: `test-results/latency-2026-11-02/{template,luna-custom,groq-custom}.json`
és `northflank-metrics.json` (ignorált helyi mérési fájlok).

## Első javítás: a referenciajellemzők újrafelhasználása

A kontúrjavítás több száz jelöltet hasonlít ugyanahhoz a rajzhoz. Korábban
minden jelölt minden irány/kezdőpont-változatánál újra meghatározta a referencia
jellegzetes fordulóit. A közös metrika most legfeljebb 128 bejegyzésben tárolja
ezeket. A kulcs pontos koordinátabájtokat, adattípust, megfigyelési skálát és
zártságot tartalmaz; nincs koordinátakerekítés. A tárolt tömb csak olvasható.
Sima, jellegzetes csúcs nélküli referencia esetén az eredményhez szükségtelen
jelöltforduló-számítás is elmarad.

Nem változott a felbontás, az irányok/fázisok száma, a keresési és javítási
keret, a kapuk küszöbe vagy az exporthoz szükséges valós utcai geometria.
A hideg benchmark és a tesztfixture az új cache-t is törli.

Egy korábban rögzített, 104 utcai pontból álló szegedi négyzet
referenciavezérelt kontúrjavításának helyi cProfile-mérése 5,88-ról 3,64 s-ra
csökkent; 211 összehasonlításnál 1650 cache-találat és 4 kihagyás történt.
Ez profilozott részfolyamat, egyetlen gépen; nem teljes éles gyorsulási arány.

Az azonos geometriás audit 145 sablon 580 perturbált párján és egy korábban
rögzített szolgáltatói útvonalon, két felbontással, **1162 összehasonlításban
bitre azonos** metrikaeredményt adott (`accuracy.json`). A 120 teljesítmény- és
útvonaljavítási teszt, valamint a 29 benchmarkteszt,
a Ruff és a teljes alkalmazás Mypy-ellenőrzése sikeres.
A teljes, páros élő routing-benchmark eredménye alább szerepel.

A régi mérőeszköz csak a `current` változatnak adott keresési seedet, mert
az eredeti, 2026. októberi alapverzió még nem támogatta azt. A mostani
`dd6d933` alapverzió már véletlen keresést használ: az első futás ezért nem
azonos keresési bemeneteket mért. Az eredményei megmaradnak a `paired/`
könyvtárban, de sebesség-összehasonlításra nem használhatók. A javított mérő
minden seedet támogató verziónak ugyanazt adja; a régi, seed nélküli verziókat
továbbra is kezeli. Eltérő seedpolitikájú korábbi bizonyítékot nem használ újra.
Az ismételt mérés helye `paired-seeded/`.

### Azonos seedes élő párok

Hat szegedi eset, mindkét verzió külön friss folyamatban és külön élő
ORS-kérésekkel, váltott AB/BA sorrendben. A táblázatban a zárójeles rész
a benchmark 35 kérés/perc korlátja miatti várakozás, amelyet a teljes idő
tartalmaz. Az időből egyszerű kivonással nem kapható tiszta CPU-idő.

| Eset | Eredeti teljes idő (kvótavárakozás) | Javított teljes idő (kvótavárakozás) | Megmaradó kapuhiba |
| --- | ---: | ---: | --- |
| szív, futás 5 km | 13,32 s (0,00 s) | 59,30 s (46,27 s) | nincs |
| csillag, futás 5 km | 91,43 s (51,26 s) | 86,78 s (47,65 s) | visszafordulás |
| háromszög, futás 5 km | 59,43 s (21,70 s) | 54,91 s (22,74 s) | hosszarány |
| kör, futás 5 km | 74,99 s (41,88 s) | 78,37 s (48,06 s) | fordulók, hosszarány |
| csillag, futás 10 km | 81,62 s (8,10 s) | 81,60 s (7,37 s) | fordulók, visszafordulás, hosszarány |
| szív, kerékpár 15 km | 59,82 s (24,73 s) | 54,05 s (12,23 s) | fordulók, hosszarány |

**Mind a hat párban pontosan azonos lett a teljes utcai geometria és a teljes
validálási eredmény.** A 12 futás megőrizte a szolgáltatói geometriát és minden
GPX-pontot, a maximális exporteltérés 0 méter. Egy-egy helyreállított
transporthiba történt: az eredeti háromszög Directions-hívásában és a javított
kerékpáros szív snap-hívásában. Nem volt 429 miatti megszakítás. A nyers HTTP
válaszok és a hibák is megmaradtak a mérési könyvtárban.

Minden pár ugyanazt az ORS 9.10.0 motort, `2026-09-20T06:31:34Z` gráfverziót
és rögzített OSM-snapshotot használta. A mérési profil 175 s workflow-keretet,
35 s optimalizálási keretet, 6 finomítást és 180 alap-elhelyezést használt;
ez nem az éles, kisebb Docker-profil teljesítménymérése. Az egyes időeredmények
vegyesek, hálózati hibát és mesterséges kvótavárakozást is tartalmaznak,
így **nem bizonyítanak általános teljes generálási gyorsulást**.
Az ellenőrzött összesítés: `paired-seeded/comparison-summary.json`.

A három éles válasz GPX-geometriáján és nyilvános referencia-előnézetén
ugyanezt a javítási keresést külön is lefuttattuk, új hálózati kérés nélkül.
Mind a hat pár **pontosan azonos javítási javaslatokat** adott:

| Rögzített bemenet | Javítás | Eredeti | Javított |
| --- | --- | ---: | ---: |
| szív | szakasz elhagyása | 2,29 s | 1,83 s |
| szív | referencia vezette | 5,01 s | 3,07 s |
| integető robot | szakasz elhagyása | 2,53 s | 2,75 s |
| integető robot | referencia vezette | 5,60 s | 3,34 s |
| esernyős robot | szakasz elhagyása | 2,28 s | 1,12 s |
| esernyős robot | referencia vezette | 2,56 s | 1,15 s |

Hideg cache, váltott sorrend, egyetlen megfigyelés páronként; az egyik
részmérés lassabb lett. Az eredmény nem általános éles gyorsulási arány.
Az előnézeti referencia nem feltétlenül a teljes belső rajzgeometria.
Bizonyíték: `recorded-repairs.json` és a mellette tárolt egyszeri mérőszkript.

## Második javítás: natív diszkrét Fréchet-számítás

A Fréchet-összehasonlítás további Python/NumPy hullámfront-ciklusokat futtatott
minden jelöltre. A már telepített Shapely 2.1.2 / GEOS 3.13.1 ugyanazt a
[diszkrét Fréchet-metrikát](https://shapely.readthedocs.io/en/2.1.2/reference/shapely.frechet_distance.html)
natív kódban is számolja. A közös batch most ezt használja, minden korábbi
iránnyal, fázissal és mintaponttal; nincs sűrítés vagy egyszerűsítés. Az üres
görbék eredménye továbbra is végtelen, az egypontos görbéket pontgeometria kezeli.
A különálló NumPy referenciaimplementáció megmarad független regressziós
összehasonlításnak. Új függőség nincs, a batch hullámfront-segédfüggvénye elmarad.

A forrásmódosítás előtti shadow-audit ismét 1162/1162 bitre azonos metrikát
adott a `dd6d933` alapverzióhoz képest (`native-shadow-accuracy.json`).
A beépített változat 127 célzott tesztje, Ruff- és Mypy-ellenőrzése sikeres;
az üres és egypontos görbék külön regressziós esetet kaptak. A tényleges
forráskód auditja a `b6abde9` cache-elt alapverzióhoz képest is 1162/1162 bitre
azonos metrikát adott (`native-accuracy.json`).

A rögzített éles geometriákon az első, már cache-elt javításhoz (`348724d`)
képest az alábbi külön részfolyamatmérések készültek:

| Rögzített bemenet | Javítás | NumPy batch | Natív batch |
| --- | --- | ---: | ---: |
| szív | szakasz elhagyása | 3,18 s | 2,73 s |
| szív | referencia vezette | 4,66 s | 2,47 s |
| integető robot | szakasz elhagyása | 3,21 s | 1,61 s |
| integető robot | referencia vezette | 5,02 s | 5,28 s |
| esernyős robot | szakasz elhagyása | 1,21 s | 0,74 s |
| esernyős robot | referencia vezette | 2,27 s | 1,09 s |

Mind a hat pár pontosan ugyanazokat a javítási javaslatokat adta.
Hideg cache, váltott sorrend, egyetlen megfigyelés páronként; az egyik mérés
lassabb lett. Ez nem általános éles gyorsulási arány. Bizonyíték:
`native-recorded-repairs.json` és a mellette tárolt egyszeri mérőszkript.

A natív változat élő, azonos seedes összehasonlítása a `b6abde9` cache-elt
alapverzióval (`native-paired/`) ugyancsak mind a hat esetben pontosan azonos
teljes utcai geometriát és validálást adott. Mind a 12 futás megőrizte a
szolgáltatói geometriát és minden GPX-pontot, a maximális exporteltérés 0 m.
A minőségi kapuk eredménye az előző táblázattal egyezett: egy teljesen sikeres
pár és öt, továbbra is felülvizsgálatot igénylő pár. Az eredeti kerékpáros szív
egy Directions-transporthibából helyreállt; 429 miatti megszakítás nem volt.

| Eset | Cache-elt alap teljes idő (kvótavárakozás) | Natív teljes idő (kvótavárakozás) |
| --- | ---: | ---: |
| szív, futás 5 km | 14,18 s (0,00 s) | 57,46 s (44,97 s) |
| csillag, futás 5 km | 92,66 s (52,99 s) | 86,27 s (49,22 s) |
| háromszög, futás 5 km | 60,10 s (24,26 s) | 54,32 s (17,54 s) |
| kör, futás 5 km | 75,37 s (42,20 s) | 78,25 s (52,92 s) |
| csillag, futás 10 km | 81,46 s (9,83 s) | 79,90 s (20,12 s) |
| szív, kerékpár 15 km | 63,35 s (33,29 s) | 60,01 s (37,02 s) |

Ugyanaz a 175 s-os helyi profil, a rögzített OSM-snapshot és az ORS 9.10.0,
`2026-09-20T06:31:34Z` gráfverzió szerepelt minden párban. A kvótavárakozás a
teljes idő része; kivonásával nem kapunk tiszta CPU-időt. Az egyedi megfigyelések,
a transporthiba és az éles Docker-profiltól eltérő keret miatt ebből sem
állítható általános éles gyorsulási arány. Ellenőrzött összesítés:
`native-paired/comparison-summary.json`.

## Éles utómérések és határidő-kezelés — 2026-11-03

Mindkét javítás teljes CI után élesbe került: a cache-javítás `b6abde9`,
a natív számítás `f776381`. A Northflank commitazonosítóját, a befejezett
rolloutot, a HTTP 200 health választ és a Secure/HttpOnly cookie-t is
ellenőriztük. A csomag végig `nf-compute-10`, a lokális és éles API-kulcsok
egyeznek. A következő, az eredetivel azonos prompt/seed/cohort kérések
egyetlen-egyetlen éles megfigyelései készültek:

| Kérés | Eredeti teljes idő | Cache-javítás | Natív számítás |
| --- | ---: | ---: | ---: |
| szív | 92,59 s | 77,50 s | 80,37 s |
| integető robot, Luna cohort | 81,59 s | 82,17 s | 83,18 s |
| esernyős robot, Groq cohort | 84,88 s | 53,79 s | 89,91 s |

Minden eredmény valós utcai geometriát és érvényes GPX-et adott; mindegyik
továbbra is felülvizsgálatot igényelt. Az AI-rajzok és az időkereten belül
elkészült javítások eltérhettek, ezért ezek nem azonos geometriás minőségi
párok, és nem bizonyítanak általános gyorsulást. A Groq-os gyorsabb cache-próba
két Groq-hívással teljesült, a lassabb natív próbában Groq után OpenCode
következett. Utóbbinál önmagában a rajzfázis 77,33 s volt; a stream egy
ismételt OpenCode-dispatch-et jelzett 45,22 s eltéréssel. A provider timeoutot
és kimeneti tokenkeret miatt hiányos választ is újrapróbálhat, a stream az
okot nem különbözteti meg. A biztos megállapítás a hívásváltás és az eltelt idő.
Bizonyíték: `live-cache/`, `live-native/` és a két release-ellenőrzés JSON-ja.

Az utómérés a már indult kontúrjavaslat-keresés túlfutását is megmutatta:
a hívó a teljes workflow-időkeret után nem illeszti utcára a javaslatokat,
de a belső ciklus addig még végigszámolta azokat. A közös `reconnect_guides`
most minden költséges összehasonlítás előtt a meglévő aktív runtime teljes
minőségi határidejét ellenőrzi, és lejáratkor üres javaslatlistát ad. Nem
állít elő részlegesen rangsorolt javaslatokat; az aktuális utcai eredmény
megmarad. A rövidebb, 35 s-os optimalizálási keret nem rövidíti a 75 s-os
minőségi keretet. Az ellenőrzés a meglévő megszakítási jelzést is kezeli.

A célzott tesztek száma 150; külön regresszió ellenőrzi mindkét javaslattípus
folytatását 40 s-nál, leállását 75 s-nál és a megszakítást az előszűrésben és
a teljes felbontású rangsorolásban is. Az inputgeometria
változatlan marad. Ruff és Mypy sikeres; a `f776381` alaphoz képesti audit
ismét 1162/1162 bitre azonos metrikát adott (`deadline-accuracy.json`).
Az azonos seedes élő páros ellenőrzés a `f776381` alaphoz képest mind a hat
esetben azonos teljes geometriát és validálást adott; a 12 futás megőrizte a
szolgáltatói geometriát és minden GPX-pontot, maximális exporteltérés 0 m.
Nem volt rögzített routing-transporthiba vagy 429 miatti megszakítás. Egy
pár minden minőségi kapun átment, öt pár mindkét változattal továbbra is
felülvizsgálatot igényelt. Bizonyíték: `deadline-paired/comparison-summary.json`.
A 175 s-os helyi profilban ez az ellenőrzés a meglevő keresés megőrzését
igazolja; a 75 s-os megszakítást a funkcionális regresszió ellenőrzi, nem egy
szintetikus sebességmérés. Ez nem szigorú HTTP-időkorlát: a már futó providerhívás és a
szükséges utcai validálás továbbra is befejeződhet, ahogyan korábban is.

Egy rövid, változatlan kódú 0,5 vCPU-s összehasonlítást is előkészítettünk.
A Northflank a `nf-compute-50` módosítást HTTP 400-zal visszautasította:
`Deployment plan nf-compute-50 exceeds your free project deployment resource allowance`.
A mérés nem indult el; a billing objektum az ellenőrzött eredetivel egyezett,
a csomag `nf-compute-10`, a deployment `COMPLETED` maradt. Nincs magasabb
csomaggal mért sebességeredmény. A CPU-keret növeléséhez előbb a szolgáltatói
erőforrás-keretet kell rendezni. Bizonyíték: `cpu-trial-state.json`.

## AI és infrastruktúra: további lehetőségek

1. **A geometriai számítás gyorsítása minden kérésnek segít.** Az egyszerű
   sablonoknál eleve nincs AI-hívás, ezért ezek késleltetését modellcsere
   nem oldja meg. A fenti optimalizálás ezt a közös szakaszt célozza.
2. **A Groq reasoning terhelésének külön próbája indokolt.** A GPT-OSS támogat
   `low` reasoning effortot; az adapter most szolgáltatói alapértéket használ.
   Csökkentése csak azonos kérések ShapeSpec-, geometriai és szemantikai
   ellenőrzése után kapcsolható be. A kisebb tokenkeret önmagában kockázatos:
   a csonka JSON újrapróbálást és szolgáltatóváltást okozhat.
   A modell a [szigorú strukturált kimenetet](https://console.groq.com/docs/structured-outputs)
   is támogatja. Az adapter jelenleg JSON-object módot használ; a sémakényszer
   alkalmazhatóságát a valódi ShapeSpec és rajzprogram sémáin külön kell
   kipróbálni, mert a szolgáltató a séma egy részhalmazát fogadja el.
3. **A meglévő AI-cache és a sablonút már elkerüli a fölösleges hívásokat.**
   Ezek helyett új AI-réteg hozzáadása további hálózati várakozást hozna.
   Az egyedi rajz két egymásra épülő hívását nem lehet egyszerűen párhuzamosítani:
   a geometria a ShapeSpec felismerési követelményeire épül.
4. **Nagyobb CPU-keret mérhető kísérletként jöhet szóba.** Azonos verzióval és
   kérésekkel, költségjóváhagyás után lehetne összehasonlítani. Az előfizetést
   ez a javítás nem módosítja; a hálózati és LLM-várakozást több CPU sem tünteti el.
   A [Northflank aktuális listaára](https://northflank.com/pricing) szerint
   a 0,5 vCPU / 1 GB csomag 12 USD/hó, az 1 vCPU / 2 GB csomag 24 USD/hó,
   folyamatos futással, a többi erőforrás díja nélkül. Ezek nem a csapat
   kreditekkel és kedvezményekkel csökkentett tényleges számlájának becslései.
5. **Az első valódi előnézetet külön kell mérni a végleges eredménytől.** Ez már
   része a streamnek és a felületnek. Nem helyettesíti a tényleges gyorsítást,
   és nem lehet ideális rajzot kész utcai útvonalként megjeleníteni.

Források: [Groq késleltetésmérési útmutató](https://console.groq.com/docs/production-readiness/optimizing-latency)
és [Groq reasoning paraméterek](https://console.groq.com/docs/reasoning).
A szolgáltatói dokumentáció alapján felsorolt lehetőségek nem alkalmazásszintű
sebesség- vagy minőségbizonyítékok. A kiválasztott GPT-6 Luna már `low`
reasoning beállítással fut; az 50–50%-os látogatóelosztás megmarad.

### További, izolált Groq-próba

A valódi ShapeAgent „bal kézzel integető robot” bemenetével az alap-, `low`
és `low` + szigorú JSON-sémás beállítást is kipróbáltuk, az éles konfiguráció
módosítása nélkül. Mindhárom ugyanazt a végső, katalógusra támaszkodó
geometriát adta. Nincs független szemantikai pontszám; ez egyetlen ismert
rajz és nem bizonyíték tetszőleges egyedi rajzok minőségére.

| Beállítás | A két HTTP-hívás összes ideje | Kimeneti token | Ebből reasoning |
| --- | ---: | ---: | ---: |
| alapérték | 11,36 s | 4728 | 3837 |
| low | 5,21 s | 1831 | 409 |
| low + strict | 6,53 s | 2607 | 389 |

A hívások között a két `low` próbában szándékosan 60 másodpercet vártunk:
a táblázat ezt a mesterséges várakozást nem tartalmazza, ezért **nem teljes
generálási idő**. Egy korábbi alapértékes próbában a két hívás 7,13 s volt;
az időingadozás is számít. Gyors egymásutánban a `low` is HTTP 429-et kapott.
A válaszfejlécek 8000 token/perc korlátot jeleztek, a visszautasítás típusa
`tokens`, az egyik `retry-after` 13 másodperc volt. A korlát szervezeti szintű;
a fejléc jelentését a [Groq rate-limit dokumentáció](https://console.groq.com/docs/rate-limits)
rögzíti. A `low` önmagában nem oldja meg a kvótát, és a burst hibákat nem
szabad gyors eredménynek számolni. A szigorú séma mindkét valódi alkalmazássémával
sikerült ebben a próbában. Bizonyíték: `groq-probe-summary.json`, valamint a
teljes és a 429-cel végződő próbák ugyanabban az ignorált könyvtárban.
