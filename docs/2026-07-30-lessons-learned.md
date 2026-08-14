# 2026-07-30 – fejlesztési és production tapasztalatok

> **2026-08-14 frissítés:** a dokumentumban szereplő „review” export kizárólag
> sikeresen, összefüggő utcahálózatra útvonalazott jelöltre vonatkozik. A
> `snapped=false` egyenes vonalas diagnosztika többé nem tölthető le: a generálás
> és a szerkesztés HTTP 503-mal, GPS-fájl nélkül áll le. A frontend közben már
> fázisokat, eltelt időt, GPS-art animációt, változó üzeneteket és megszakítási
> lehetőséget mutat.

Ez a dokumentum a 2026. július 30-i fejlesztési, kutatási,
üzemeltetési és hibakeresési tapasztalatokat rögzíti. Célja, hogy a mai
döntések indoklása, a production incidensek oka és a bevált diagnosztikai
lépések később is visszakereshetők legyenek.

Az itt szereplő időpontok UTC-ben értendők, ha nincs külön jelezve.
API-kulcsot, hozzáférési tokent vagy más titkot a dokumentum nem tartalmaz.

## Vezetői összefoglaló

A nap végére a projekt:

- felismerhetőségi pontszám alapján rangsorolja, de nem törli a gyengébb
  jelölteket;
- legfeljebb 180 városi elhelyezést vizsgál meg egy olcsó ORS snap
  előszűrésben;
- hét eltérő, jó minőségű elhelyezést tart meg a drágább Directions
  útvonaltervezés számára;
- megőrzi a preflight diagnosztikát és minden ténylegesen útvonalazott
  candidatet;
- kézi térképes szerkesztést, újraútvonalazást és GPX/TCX exportot biztosít;
- strukturált, request ID-val összekapcsolható JSON naplót ír;
- Northflankon egyetlen FastAPI-konténerből szolgálja ki az API-t és a
  React felületet;
- Grafana Cloud Loki felé továbbítható, tartósan kereshető logokat ad;
- ugyanazt a Budapest–szív útvonalat productionben 203,98 másodperc helyett
  25,5 másodperc alatt készíti el.

A nap két production problémája:

1. Az alkalmazás először csak `127.0.0.1:8000` címen figyelt, ezért a
   Northflank proxy `connection refused` hibát kapott.
2. A hostbeállítás javítása után a backend ugyan sikeresen generált, de a
   203,98 másodperces feldolgozás túllépte a frontend 180 másodperces
   időkorlátját. A valódi szűk keresztmetszet a 180 zárt preflight-jelölt
   szükségtelenül nagy, 256 pontos, kvadratikus Fréchet-összehasonlítása volt.

Mindkét hibát mérés és request ID-val korrelált logok alapján azonosítottuk.

## A mai változások és kiadások

| Commit | Tartalom |
|---|---|
| `63d6b76` | GPS-art generálás, jelöltkezelés és online útvonalszerkesztő újraépítése |
| `d075a48` | A GPS-art algoritmus tudományos hátterének dokumentálása |
| `f606ae0` | Northflank deployment és Grafana-kompatibilis naplózás előkészítése |
| `0b16f86` | Anthropic válaszkezelés típusjavítása |
| `78621df` | A zárt útvonalak preflight pontozásának production gyorsítása |

A jelenlegi production cím:

<https://p01--cityshaperunner--vnycn2g6bghl.code.run/>

Health endpoint:

<https://p01--cityshaperunner--vnycn2g6bghl.code.run/health>

Elvárt válasz:

```json
{
  "status": "ok",
  "service": "GPS Art Wizard",
  "version": "0.1.0"
}
```

## GPS-art minőségi tanulságok

### A sikeres útvonal még nem feltétlenül felismerhető rajz

Az, hogy egy routing szolgáltató minden waypoint között talál járható utat,
csak hálózati összeköttetést bizonyít. Nem bizonyítja, hogy:

- megmaradt a sziluett;
- megmaradtak a jellegzetes csúcsok és irányváltások;
- nem keletkezett aránytalan kerülő;
- megfelelő a rajz méretaránya;
- ember számára első pillantásra felismerhető az alakzat.

Ezért az alkalmazás külön méri:

- az útvonal és a referencia közös koordinátarendszerben vett eltérését;
- a Fréchet- és Hausdorff-alapú térbeli hasonlóságot;
- a kontúr lefedettségét;
- a jellegzetes fordulatok sorrendjét;
- a hossz- és kiterjedésarányokat;
- a célhossz illeszkedését;
- zárt rajzoknál a záródást;
- azt, hogy valódi Directions útvonal készült-e.

A részletes tudományos háttér a
[GPS-art kutatási jegyzetben](gps-art-research.md) található.

### Az `expected1` és `expected2` vizuális referenciák tanulságai

A két referenciaábra nem pusztán „szép képet”, hanem jól olvasható
termék-visszajelzést is mutat:

- a vastag kék vonal a ténylegesen útvonalazott eredmény;
- a szaggatott rózsaszín vonal az ideális kontúr;
- a zöld pontok a fontos kontroll- vagy horgonypontok;
- a térkép teljes alakzatot befogó nézete segíti az azonnali felismerést;
- a candidate-kártyákon együtt látszik a forma, táv, rang és minőség.

Az `expected1` heart-arrow példában a felismerhetőség kulcsa, hogy külön
megmarad:

- a két felső szívlobusz;
- a középső bemetszés;
- az alsó csúcs;
- a nyíl szára és iránya.

Az `expected2` nyílnál a nyílhegy szélessége, a tengely folytonossága és a
farokrész elkülönülése fontosabb, mint az apró utcai cikkcakkok. A nagy
léptékű topológiának kell stabilnak maradnia.

További konkrét tanulságok:

- az ideális és a route-olt kontúr együttes megjelenítése nélkül a
  felhasználó nem tudja megítélni, hol rontott a router;
- a jellegzetes csúcsokat nagyobb súllyal kell kezelni, mint a kevésbé fontos
  ívközi pontokat;
- a score önmagában nem elég: a képeken látható 46–54%-os érték mellett az
  ember még felismerhet alakzatot, ezért emberi címkékkel kell kalibrálni;
- a három közel azonos kártya azt mutatja, hogy a top-*k* lista könnyen
  duplikátumokat ad; a shortlistnek minőség mellett térbeli és
  transzformációs változatosságot is kell biztosítania;
- az alakzatot befogó automatikus map fit, az egyértelmű vonalhierarchia és a
  kontrollpontok szerkeszthetősége a minőség része, nem csupán UI-díszítés.

### A város és az alakzat illeszkedése külön optimalizálási probléma

Ugyanaz a rajz nem helyezhető rá minden városra azonos minőségben. A
felismerhetőséget befolyásolja:

- az utcahálózat rácsossága vagy sugaras szerkezete;
- folyók, tavak, vasutak és gyorsforgalmi utak;
- parkok és korlátozottan járható területek;
- a gyalogos és kerékpáros hálózat eltérése;
- az alakzat konkáv részeinek és csúcsainak iránya;
- az elérhető városi terület és a kért táv.

Az alkalmazás ezért eltolást, forgatást és skálázást is vizsgál. Ha egy
kifejezetten kért forma a teljes, mért útvonalon nem éri el a minőségi
kapukat, egyszerűbb, városhoz illő alternatívákat is megmér. Az eredeti
jelöltet nem szabad eltüntetni: a helyettesítés indoklását és az összehasonlító
pontszámokat is meg kell mutatni.

### A quality gate rangsoroljon, auditáljon, és védje az exportot

A mai fontos termékdöntés: rosszabb pontszám miatt egy candidatet sem szabad
csendben eldobni.

Megkülönböztetendő:

- **preflight candidate:** olcsó, független útszegély-snap alapján pontozott
  elhelyezés; nem exportálható útvonal;
- **fully routed candidate:** ORS Directions által összekötött, teljes
  polyline-nal és végső validációval rendelkező útvonal.

Minden preflight eredmény bekerül a diagnosztikába. A Directions-kvóta miatt
csak a minőség és változatosság alapján kiválasztott shortlist kerül teljes
útvonalazási sorba. Minden ténylegesen útvonalazott jelölt megmarad az
auditban. A választóban minden, a végleges kiválasztott alakzathoz tartozó
útvonal megjelenik: az automatikus célokat teljesítők „verified”, a többi
„review” jelöléssel. Utóbbiak GPX-e csak kifejezett felhasználói elfogadás után
tölthető le. Így nincs csendes adatvesztés, és a tudományos mérés sem veszi el
a felhasználótól a végső vizuális döntést.

### A kézi korrekció a professzionális folyamat része

A teljesen automatikus útvonaltervező nem tud minden helyi gráfhibát,
átjárhatósági változást vagy vizuálisan zavaró kerülőt tökéletesen kezelni.
Ezért a felhasználó:

- kiválaszthat bármely, a kért alakzathoz tartozó teljes candidate-et;
- számozott kontrollpontokat húzhat a térképen;
- az új guide-ot ismét elküldheti az aktivitásspecifikus routernek;
- megkapja az új távolságot és minőségi pontszámot;
- az eredményt automatikus validáció után közvetlenül, vagy a mért eltérések
  megismerése és kifejezett elfogadás után töltheti le GPX- és TCX-formátumban.

A szerkesztett guide sem címkézhető valódi utcai útvonalnak, ha a Directions
hívás sikertelen. A jelenlegi fail-closed szerződés ilyenkor HTTP 503 választ ad
és nem készít GPX/TCX fájlt; a felhasználó megtarthatja a pontjait és újra
próbálhatja az útvonalazást.

## Dokumentációs és GitHub-tapasztalatok

A README akkor segíti a projekt használatát, ha a marketingállítások mellett
az algoritmus korlátait és tudományos eredetét is bemutatja. A mai frissítés:

- különválasztja a publikált kutatási eredményt és a projekt mérnöki
  közelítését;
- közvetlenül hivatkozik a GPS-art, shape matching, route-choice és
  map-matching forrásokra;
- kimondja, hogy az ORS-re épülő rendszer nem azonos a tanulmányok egyedi
  gráfkereső algoritmusaival;
- dokumentálja a candidate-megőrzést és a kézi korrekciót;
- production és observability útmutatóhoz irányít.

Releváns badge-ek:

- CI;
- Python és Node verzió;
- FastAPI és React;
- Docker readiness;
- Northflank deployment readiness;
- Grafana Cloud logolás.

A badge csak akkor hasznos, ha kattintható és a mögötte lévő állapothoz vagy
dokumentációhoz vezet. Nem érdemes olyan dísz-badge-et használni, amely nem
ellenőrizhető vagy elavulhat anélkül, hogy a CI jelezné.

## Hosting- és adattárolási tapasztalatok

### Koyeb

A Koyeb címet a használt hálózat AI-alapú fenyegetésészlelése blokkolta. Ez
nem alkalmazáshiba volt, de a felhasználói elérhetőséget ellehetetlenítette,
ezért másik hostra volt szükség.

Tanulság: hosting választásakor nem elég az ár és a technikai kompatibilitás.
A tényleges felhasználói hálózatból is ellenőrizni kell:

- a szolgáltatói domaint;
- a TLS-tanúsítványt;
- a DNS-feloldást;
- a vállalati vagy ISP-szűrők viselkedését.

### Northflank

A kiválasztott Northflank Developer Sandbox erőforrása:

- `0.1 vCPU`;
- `256 MB` memória;
- `1024 MB` ideiglenes tárhely.

Ez megfelelő lehet hobby- és tesztkörnyezetnek, de a `0.1 vCPU` a
CPU-intenzív, kvadratikus geometriai algoritmusokat körülbelül egy
nagyságrenddel lassíthatja. A lokális fejlesztői gépen elfogadható algoritmust
mindig újra kell mérni a tényleges production compute planen.

Az alkalmazás ugyanabban a konténerben szolgálja ki:

- a FastAPI végpontokat;
- a buildelt React SPA statikus fájljait;
- a health endpointot;
- a memóriában generált GPX/TCX tartalmat.

### Hol vannak a fájlok?

Productionben:

- a GPX és TCX a kérés során memóriában készül;
- a böngésző tölti le a fájlt;
- az ideiglenes konténerfájlrendszer nem tekintendő tartós tárolásnak;
- `EXPORT_DIR` maradjon üres, ha nincs explicit persistent volume;
- `LOG_FILE` maradjon üres, mert a Northflank a konzolkimenetet gyűjti.

Tartós alkalmazáslogot nem a konténerben, hanem a Northflank logstreamből
Grafana Cloud Lokiban kell megőrizni.

A Loki logtároló nem általános GPX-fájltár. A felhasználói exportokat a
böngésző tölti le; későbbi szerveroldali route-könyvtárhoz külön objektumtár
vagy adatbázis szükséges.

## Grafana Cloud és kereshető naplózás

A létrehozott Grafana Cloud stack a felületen 14 napos trialt jelzett. A trial
lejárta előtt ellenőrizni kell az aktuális Free csomag log-ingest,
retention- és felhasználói korlátait. A projekt ne támaszkodjon trial-only
funkcióra anélkül, hogy a free-tier működést külön igazolná.

Az alkalmazás egy soros strukturált JSON-t ír `stderr`-re. Fontos mezők:

- `timestamp`;
- `severity`;
- `service`;
- `environment`;
- `logger`;
- `request_id`;
- `event`;
- `duration_ms`;
- az adott fázisra jellemző minőségi és darabszámmezők.

Minden HTTP-kérés kap `X-Request-ID` választ. A frontend, a backend,
az OpenRouteService-hívások és a generálási fázisok ugyanazzal az
azonosítóval kereshetők.

Ajánlott Grafana/Loki keresések:

```logql
{host="Northflank"} |= "gps-art-wizard"
```

```logql
{host="Northflank"} |= "\"severity\":\"ERROR\""
```

```logql
{host="Northflank"} |= "\"event\":\"generation.completed\""
```

```logql
{host="Northflank"} |= "\"event\":\"preflight.scoring.completed\""
```

```logql
{host="Northflank"} |= "\"request_id\":\"994d7b87-a335-40e6-aab5-c06e735259ca\""
```

Ha a sink közvetlenül parse-olható JSON-t ad:

```logql
{host="Northflank"}
| json
| event="preflight.scoring.completed"
```

Biztonsági szabályok:

- prompt teljes szövege ne kerüljön logba;
- API-kulcs és token soha ne kerüljön logba;
- a Grafana `logs:write` token a Northflank log sink titka legyen;
- a request ID keresési kulcs, ne magas kardinalitású Loki label legyen.

A teljes bekötési leírás a
[deployment dokumentációban](deployment.md#persistent-and-searchable-grafana-cloud-logs)
található.

## Production incidens 1: `connection refused`

### Tünet

A publikus Northflank URL ezt adta:

```text
upstream connect error or disconnect/reset before headers
remote connection failure
delayed connect error: Connection refused
```

A Northflank felületen:

- a build sikeres volt;
- a pod `Running` állapotot mutatott;
- nem volt restart;
- a deployment mégis `Waiting` állapotban maradt;
- a `/health` publikus végpont HTTP 503-at adott.

### Bizonyíték

A korai runtime log:

```text
Uvicorn running on http://127.0.0.1:8000
```

A helyi `.env` fejlesztői értéke:

```dotenv
API_HOST=127.0.0.1
API_PORT=8000
```

Ez helyben helyes, konténeres ingress mögött viszont nem. Ha a helyi `.env`
változtatás nélkül kerül a Northflank Environment részébe, felülírja a
Dockerfile production alapértékét.

### Gyökérok

Az Uvicorn csak a konténer loopback interfészén figyelt. A Northflank sidecar
és ingress más hálózati interfészről próbált kapcsolódni, ezért kapott
`connection refused` hibát.

### Javítás

Northflank runtime változók:

```dotenv
APP_ENV=production
API_HOST=0.0.0.0
API_PORT=8000
```

Ha kézzel megadott `PORT` változó létezik, azt törölni kell, vagy `8000`
értékre kell állítani. A jelenlegi alkalmazás a `PORT` értékét előnyben
részesíti az `API_PORT` előtt.

Networking:

- internal port: `8000`;
- protocol: `HTTP`;
- publicly exposed: igen;
- a Dockerfile `EXPOSE 8000` értékét kell használni.

Health check:

- readiness HTTP;
- port `8000`;
- path `/health`;
- alacsony CPU mellett legalább 30 másodperces initial delay ajánlott.

A helyes új log:

```text
Uvicorn running on http://0.0.0.0:8000
```

Ezután a `/health` és `/` végpont is HTTP 200-at adott.

### Fontos logértelmezés

Ezek a sorok önmagukban nem hibák:

```text
Shutting down
Application shutdown complete.
Finished server process
Process terminated.
```

Ha közvetlenül environment-módosítás vagy új deployment után jelennek meg,
szabályos SIGTERM-alapú rolloutot jeleznek. Crash esetén traceback,
nem nulla kilépési kód, restartnövekedés vagy `OOMKilled` jelzés is várható.

## Production incidens 2: a backend elkészíti, a frontend mégis hibát mutat

### Felhasználói tünet

Az oldal ezt jelezte:

```text
No candidate created
We couldn’t find a route for this idea
The route service took too long to respond. Please try again.
```

Lokálisan ugyanez a kérés jóval korábban elkészült.

### Korrelált production timeline

Request ID:

```text
93276b6b-4ee1-4439-a179-09a39a6e2e58
```

| Idő | Esemény |
|---|---|
| `20:25:48.874` | `generation.requested`, Budapest, heart, run, 8 km |
| `20:25:49.144` | 401 alakzatpont elhelyezve |
| `20:25:57.792` | ORS `/v2/snap/foot-walking/json` → HTTP 200 |
| `20:29:10.246` | 180 elhelyezés preflight pontozása befejeződött |
| `20:29:10.924` | ORS Directions → HTTP 200 |
| `20:29:12.746` | validáció és GPX export kész |
| `20:29:12.842` | `/generate` → HTTP 200, `duration_ms=203975.52` |

A backend tehát sikeresen elkészítette az eredményt. A frontend
`frontend/src/api.js` generálási timeoutja 180 000 ms volt, ezért körülbelül
24 másodperccel a backend válasza előtt megszakította a kérést.

### Miért nem a timeout egyszerű növelése lett a megoldás?

A hosszabb timeout csak elfedte volna a túl lassú algoritmust:

- rosszabb felhasználói élményt adott volna;
- tovább foglalta volna a 0,1 vCPU-s példányt;
- több párhuzamos kérésnél gyorsan torlódást okozott volna;
- más proxy- vagy böngésző-időkorlátba ütközhetett volna.

Először a fázisok időbélyegei alapján a valódi CPU-szűk keresztmetszetet
kellett megszüntetni.

### Gyökérok az algoritmusban

A preflight legfeljebb 180 transzformációt készít:

- 3 skála;
- 6 forgatás;
- városi és lokális eltolások;
- legfeljebb 18 görbületmegőrző guide-pont candidatenként.

Az ORS snap válasza után minden zárt guide hasonlóságát a rendszer 64 pontos
preflight-kérés ellenére legalább 256 mintaponton számolta. A diszkrét
Fréchet-távolság `O(n²)` időigényű, ezért a felesleges négyszeres
mintaszám körülbelül tizenhatszoros elméleti belső munkát jelentett.

Ez a magas felbontás indokolt a végső útvonal validációjánál, de nem indokolt
egy legfeljebb 18 guide-pontos, durva előszűrésnél.

### Javítás

A `similarity_diagnostics_between_routes` új
`closed_sample_floor` paramétert kapott:

- alapérték: `256`;
- végső validáció: változatlanul `256`;
- preflight: `64`.

Így:

- egyetlen preflight candidate sincs kihagyva;
- mind a 180 elhelyezés ugyanúgy pontszámot kap;
- csak az előszűrés numerikus felbontása igazodik a bemenet tényleges
  részletességéhez;
- a végső Directions-útvonal minőségi ellenőrzése változatlan marad.

Új strukturált logesemény:

```text
event=preflight.scoring.completed
```

Kapcsolódó mezők:

- `candidate_count`;
- `sample_count`;
- `duration_ms`.

Commit:

<https://github.com/ak91hu/CityShapeRunner/commit/78621df41bf4331c429ce823588c0c56a1737fe2>

Northflank build:

```text
nice-guide-739
```

### Teljesítménymérések

| Mérési pont | Javítás előtt | Javítás után | Eredmény |
|---|---:|---:|---|
| 180 azonos zárt hasonlóság lokálisan | 18,640 s | 1,613 s | 11,6× gyorsabb |
| Teljes Budapest–szív generálás lokálisan | 20,2 s | 3,732 s | kb. 5,4× gyorsabb |
| Teljes Budapest–szív generálás Northflankon | 203,98 s | 25,5 s | kb. 8× gyorsabb |

A javítás előtti és utáni végső eredmény azonos maradt:

| Mutató | Érték |
|---|---:|
| Preflight elhelyezések | 180 |
| Kiválasztott alakzat | `heart` |
| Validációs pontszám | `0.815503023422733` |
| Shape fidelity | `0.738821050221819` |
| Úthálózatra illesztve | igen |
| Végső pontok | 136 |
| Távolság | 7,47 km |

Az éles ellenőrző kérés request ID-ja:

```text
994d7b87-a335-40e6-aab5-c06e735259ca
```

## Northflank referencia-konfiguráció

### Build és futtatás

- service type: Combined;
- repository: `ak91hu/CityShapeRunner`;
- branch: `master`;
- build type: Dockerfile;
- build context: `/`;
- Dockerfile: `/Dockerfile`;
- CMD override: üres;
- image CMD: `gps-art-wizzard`.

### Runtime változók

```dotenv
APP_ENV=production
SERVICE_NAME=gps-art-wizard
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE=
EXPORT_DIR=
LLM_PROVIDER=opencode
LLM_FALLBACK=opencode
ORS_CONTINUE_STRAIGHT=false
ORS_PREFERENCE=shortest
```

Külön, maszkolt secretként kezelendő:

```dotenv
ORS_API_KEY=...
OPENCODE_API_KEY=...
```

A lokális `.env` fájlt nem szabad változtatás nélkül feltölteni. Különösen
ellenőrizendő:

- `API_HOST`;
- `PORT`;
- lokális Ollama URL;
- fejlesztői CORS origin;
- minden felesleges vagy már lejárt provider token.

### Health check ajánlás

Readiness:

```text
protocol: HTTP
port: 8000
path: /health
initial delay: 30 s
interval: 10 s
timeout: 5 s
max failures: 12
```

Lassú indulás esetén külön startup probe használható, hogy a readiness és
liveness ne büntesse az import- és inicializációs időt.

## Hibakeresési döntési tábla

| Tünet | Legvalószínűbb ok | Első ellenőrzés |
|---|---|---|
| Publikus 503 és `connection refused` | rossz host vagy port | Uvicorn bind sor, Networking port |
| `Uvicorn ... 127.0.0.1:8000` | helyi `.env` felülírta a production hostot | `API_HOST=0.0.0.0` |
| `Uvicorn ... 0.0.0.0:8080`, de Networking 8000 | `PORT` felülírta az `API_PORT` értékét | `PORT` törlése vagy 8000 |
| Pod `Running`, de `Waiting`, restart nélkül | readiness nem érte el az appot | `/health`, probe port/path |
| `Shutting down` közvetlenül deploy után | szabályos rollout | deployment timestamp |
| `exit 137` vagy `OOMKilled` | elfogyott a memória | Northflank memory graph |
| `/health` 200, de generálás timeout | hosszú szinkron pipeline | request ID és fázis-időbélyegek |
| ORS snap 200 után hosszú csend | lokális pontozási CPU-forrópont | `preflight.scoring.completed` |
| Backend később 200, frontend már hibás | frontend/proxy timeout rövidebb | backend `duration_ms`, frontend timeout |
| ORS 401/403 | hibás vagy hiányzó API-kulcs | secret group, kulcsjogosultság |
| ORS 429 | kvóta vagy rate limit | retry megszüntetése, kvótaellenőrzés |
| ORS 2009 | waypointok nem köthetők össze | failing pair és bounded waypoint reduction |
| ORS 2010 | nincs közeli routable edge | korlátozott radius widening |

## Bevált production hibakeresési sorrend

1. Nyisd meg közvetlenül a `/health` végpontot.
2. Ellenőrizd a legfrissebb runtime logot, ne csak a build logot.
3. Keresd meg az Uvicorn host- és portsorát.
4. Hasonlítsd össze a logolt portot a Northflank Networking porttal.
5. Ellenőrizd a readiness/startup probe portját és pathját.
6. Egy problémás generálást request ID alapján kövess végig.
7. Írd ki a fázisok közti időket; ne csak az utolsó hibasort nézd.
8. Ellenőrizd a CPU- és memóriagrafikont.
9. Különítsd el a külső API várakozását a helyi CPU-feldolgozástól.
10. Optimalizálás után ugyanazzal a prompttal és ugyanazon minőségi
    metrikákkal végezz előtte–utána mérést.

## Verifikáció

A `78621df` javítás után:

- Ruff: sikeres;
- célzott route-engine tesztek: 66 sikeres;
- teljes pytest: 87 sikeres, 1 külső Starlette deprecation warning;
- mypy `--ignore-missing-imports` mellett: sikeres;
- valós ORS Budapest–szív generálás lokálisan: sikeres;
- valós ORS Budapest–szív generálás Northflankon: HTTP 200, 25,5 s;
- a javítás előtti végső score, fidelity, távolság és pontszám változatlan.

Ismert fejlesztői környezeti hiányosság:

- a szigorú mypy futtatáshoz jelenleg hiányzik a `types-PyYAML` és a
  `types-shapely` stubcsomag;
- ez nem production runtime hiba, de a CI típusellenőrzés teljes
  szigorúságához később felveendő a dev dependency-k közé.

Windows alatt a pytest alapértelmezett felhasználói temp mappája
`PermissionError` hibát adott. Megbízható ellenőrzéshez workspace-en belüli
explicit base temp használható:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp .codex-test-temp/pytest-full
```

## További fejlesztési irányok

### Rövid táv

- **Elkészült 2026-08-14:** a frontend fázisalapú, GPS-art-specifikus várakozási
  állapotot, eltelt időt, változó üzeneteket és megszakítást mutat a végtelen
  spinner helyett.
- A `generation.completed` mellett minden drága fázis kapjon
  `*.started` és `*.completed` eseményt.
- A production health válasz vagy response header tartalmazzon release
  revisiont, hogy az aktuális deployment kívülről azonosítható legyen.
- A Northflank és Grafana dashboardon külön panel mutassa a generálási p50,
  p95 és max időt.
- A hiányzó mypy stubok kerüljenek a dev dependency-k közé.

### Középtáv

- A hosszú generálás legyen aszinkron job:
  `POST /generate` → job ID, majd progress polling vagy Server-Sent Events.
- A fázisok időkeretet és cancellation tokent kapjanak, hogy a böngésző által
  megszakított kérés ne fogyasszon tovább feleslegesen ORS-kvótát és CPU-t.
- Készüljön per-city, per-shape benchmark corpus felismerhetőségi és
  válaszidő-regresszióhoz.
- Emberi értékelésekkel kalibrált score-threshold készüljön az
  expected referenciaábrák minőségéhez.
- A preflight shortlist mérete és a transzformációs rács compute planhez
  igazítható legyen, miközben minden proxy candidate diagnosztikája megmarad.

### Üzemeltetési elv

Ha a minőség és a válaszidő konfliktusba kerül, először:

1. profilozni kell;
2. a bemenet részletességéhez kell igazítani az olcsó előszűrést;
3. változatlanul kell hagyni a végső, felhasználói minőséget eldöntő
   nagy pontosságú validációt;
4. azonos inputon, azonos score-ral kell bizonyítani, hogy az optimalizálás
   nem rontotta a GPS-art felismerhetőségét.

Ez a mai incidens legfontosabb általánosítható tanulsága.
