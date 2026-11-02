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
