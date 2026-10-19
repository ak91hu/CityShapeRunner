# Kreatív városi elhelyezés: páros összehasonlítás

Dátum: 2026-10-19. A [kutatási és kódellenőrzés](../research/2026-10-19-generation-review.md)
leírja a vizsgált módszereket és a shortlist javítását.

## Reprodukálható mérési feltételek

Az összehasonlítás az új javítás előtti és utáni munkapéldány külön
forrásmásolatát futtatja. Nem a régi HEAD-et hasonlítja a teljes, több feladatból
származó munkapéldányhoz. A forrásmásolatok, SHA-256 lenyomatok, a teljes
ORS-pontlisták, szolgáltatói verzióadatok, hibák és időadatok a
`test-results/creative-fit-2026-10-19/` bizonyítékcsomagban vannak.

Azonos alakzat, sport, táv, város, esetszámból származtatott keresési mag és
rögzített OSM-pillanatkép mellett minden futás külön folyamatban, új élő ORS
kérésekkel dolgozik. A sorrend páronként AB/BA váltakozik. A futások közötti
kvótavárakozás a generáláson kívül történik. A futáson belüli kvótavárakozás
külön is szerepel a nyers eredményben; a határidő miatt ez a keresést is
befolyásolhatja, nem pusztán levonható zaj.

A tervezés katalógusalapú, determinisztikus módban futott (`GEOCODE_OFFLINE=1`,
`LLM_USAGE_MODE=essential`, kikapcsolt AI-kép- és útvonal-felülvizsgálat).
A futó- és úthálózati alapbeállítások azonosak voltak. Ez nem szabad szövegből
generált AI-alakzatok vagy élő geokódolás sebességmérése.

A minta három külön maggal megismételt szegedi 5 km-es futó háromszög, három
szegedi 5 km-es négyzet és egy budapesti háromszögpár. Budapest kívül esik a szegedi OSM-pillanatképen;
ott a helyi gráf nem szolgáltat területi előszűrési bizonyítékot. A végső utcai
geometriát mindkét városban élő ORS adja. A mérés az alapkonfigurációra vonatkozik,
nem a 256 MB-os konténerprofilra.

## Eredmények

**Mind a hét párban pontosan azonos maradt a végső utcai pontlista és mind a
11 összehasonlított minőségi komponens.** A 14 futás mindegyikének végső
geometriája a szolgáltatótól származik, a GPX minden pontot megőrzött, a mért
exporteltérés 0 méter. A 441 élő HTTP-kérésből nem rögzítettünk szolgáltatói hibát.
A párok ORS-motorverziója és gráfrevíziója azonos; a natív alakhűség utólagos
újraszámítása is egyezik. Az ellenőrzött motor 9.10.0, gráfdátum
2026-09-20, OSM-dátum 2026-09-13.

| Eset | Idő előtte → utána, s | Alakhűség mindkét oldalon | Minden kapu teljesült? | Directions előtte → utána |
| --- | ---: | ---: | --- | ---: |
| Szeged, háromszög, 0. mag | 18.255 → 17.571 | 80.710035% | Nem: fordulatok | 29 → 29 |
| Szeged, háromszög, 1. mag | 18.744 → 20.056 | 80.710035% | Nem: fordulatok | 31 → 31 |
| Szeged, háromszög, 2. mag | 17.264 → 17.303 | 80.710035% | Nem: fordulatok | 28 → 28 |
| Budapest, háromszög | 16.425 → 16.027 | 77.969363% | Nem: fordulatok, kerülők | 23 → 23 |
| Szeged, négyzet, 0. mag | 17.931 → 15.447 | 86.065016% | Igen | 27 → 27 |
| Szeged, négyzet, 1. mag | 14.847 → 14.858 | 86.065016% | Igen | 27 → 28 |
| Szeged, négyzet, 2. mag | 14.705 → 14.411 | 86.065016% | Igen | 27 → 27 |

A magok itt az esetszámok megnevezései; a tényleges 32 bites magot az esetazonosító
SHA-256 lenyomatának első négy bájtja adja. A pontos értékek a JSON-ban vannak.
A rövidített időadatok kerekítettek; a CSV és JSON teljes pontosságú.

Az egyedi futások 14.411–20.056 másodpercig tartottak. Ez a minta **nem bizonyít
általános gyorsulást**. Egy párban egy további Directions-hívás történt, mert a
másik kezdeti elhelyezés más útvonalváltozatot igényelt; a kezdeti elhelyezések
száma három maradt. A futáson belüli kvótavárakozásként mért intervallumok
összesített unióideje 0.176 másodperc volt. Ez a műszer a rövid zárolási várakozást
is beleszámíthatja; az extra, futások közötti lehűlési idő nincs a fenti időadatokban.

## Változatosság: mit bizonyít a mérés?

A három külön maggal mért szegedi háromszög **1/3 különböző végső útvonalat** adott
előtte és utána is; a három négyzet szintén **1/3-at**. A kész útvonalak
befoglaló téglalapjának közepe 0 méterre tért el, a 150 méteres, eltolt rácsokon
mért lefedés átfedése 100% volt. Ezt nem szabad változatos végső ajánlásnak nevezni.

A keresett és ténylegesen közúton megmért alternatívák helye változik. A javítás
az 1. négyzetes ismétlés harmadik shortlist-helyén másik elhelyezést választott:
az eredeti középponttól mért észak/kelet eltolás `(1148, -997)` méterről
`(2095, 913)` méterre változott, kerekítve. Az ehhez az elhelyezéshez tartozó
utcai változatok legjobb mért alakhűsége 33.00%-ról 62.09%-ra nőtt. Mindkettő
elbukik a teljes minőségi feltételrendszeren; ezért a jobb végső ajánlás maradt.
A HTML a teljes utcai pontlistákból rajzolja ki a régi és új jelölteket, azonos
földrajzi keretben. A legközelebbi utcára vetített vezérpontok nem szerepelnek
valódi útvonalként ezeken az ábrákon.

**Következtetés:** a pontosság ezen a mintán megmaradt, és a jelöltválasztás hibája
javult. Az első ajánlás ismétlődésének teljes megszüntetése nincs igazolva.
A korábbi „ne romoljon a pontosság” követelmény szerint a legjobb mért ajánlás
marad az alapértelmezés. Egy kisebb pontszámú, de kapukon átmenő útvonal kedvéért
történő környékváltás külön termékszabály lenne. A háromszög mérési hibája pedig
további alakillesztési munkát igényel; az ellenőrzések lazítása nem javítás.

A felhasználó megerősített döntése: **maradjon a legpontosabb ajánlás; a
választható alternatívák legyenek változatosak**. Az első ajánlás ismétlődése így
megengedett. A javítás a különböző környékekről származó, valódi utcai jelöltek
keresését érinti; a gyengébb jelöltek minőségi figyelmeztetése megmarad.

## Ellenőrzések és forrásazonosság

- Teljes backend: **889 sikeres teszt**, `backend-final.xml`.
- Célzott keresési és teljesítménytesztek: **45 sikeres teszt**.
- Ruff és mypy: sikeres, 71 ellenőrzött Python-forrásmodul.
- Dokumentáció: 55 Markdown-fájl elhelyezése és helyi hivatkozásai érvényesek;
  a szigorú MkDocs-build sikeres.
- A HTML-jelentést Chromiumban asztali és 390 px széles mobilnézetben is
  ellenőriztük: nincs oldalirányú kilógás vagy JavaScript-hiba, a mérési részletek
  nyithatók; `report-browser-check.json`.
- A végleges closure-kezelési lintjavítás és az élő mérésben használt változat
  **500 bemeneten azonos shortlistet** adott; `source-equivalence.json`.
- A numerikus pontossági audit a HEAD eredeti pontozóját hasonlítja a mostanihoz:
  **145 alakzat, 580 katalógusgeometria-pár és 3 egyedi rögzített szolgáltatói
  geometria-pár, összesen 1166 metrika-összevetés, bitre azonos eredmények,
  legnagyobb eltérés 0**. Az ismétlődő szolgáltatói geometriákat deduplikálja.
  A kilenc védett minőségi és geometriai forrás változatlan. Ez külön bizonyíték
  a páros generálási eredmények mellett; `accuracy-audit.json`.

Az előtte-forrás SHA-256 értéke `a7ce9a2d4997ed7ceff1c296fdfa854ff3da8b76d5438ce3f073fe402e89b6fe`,
az utána-forrásé `155035bc7e774c6a187d977d85cf9f42f763760a31f9f5d1b7698a412baed9c0`.
Az első utána-futás fejlécében még a két később hozzáadott magyarázó megjegyzés
nélküli előzmény lenyomata szerepel. Ennek pontos forrásmásolata is megvan,
lenyomata `1efe52932ffb7b6b4665a624d83b2e42fd9d443d89aee42e6265385fc16d27c0`;
az AST-azonosságot külön ellenőriztük. A nyers futási adatot nem írtuk át.
A végleges lintjavítás az összehasonlítási lista felépítését változtatja meg,
nem a kiválasztás eredményét; külön ekvivalenciabizonyíték tartozik hozzá.

A részletes összehasonlítás `comparison.html`, a gépi adatok `summary.json`,
`records.json` és `comparison.csv` néven találhatók a bizonyítékcsomagban.

## Korlátok

Két katalógusalakzat, két város, kevés ismétlés nem ad általános p95 válaszidőt vagy
minden alakzatra érvényes minőségi garanciát. A számszerű alakfelismerési
ellenőrzések nem helyettesítik a független emberi értékelést. A minőségi kapun
elbukott, de közúton vezető eredmény diagnosztikai összehasonlítás; nem tekinthető
automatikusan elfogadott GPS-artnak.

Az első, futások között még nem elkülönített kvótaablakú kísérletet megszakítottuk;
naplója és az addig teljesült előtte-futás az `initial-quota-interference/`
alkönyvtárban maradt. Ezt nem számítjuk a végleges párok közé. A külső
mérésszervező azonos fájlra történő kvótafájl-másolási hibája után a teljes
eredmények megmaradtak, a további futások ezek újraírása nélkül folytatódtak.
