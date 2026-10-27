# Útvonaltervezési hibák vizsgálata — 2026. október 27.

## Megfigyelések

Az ellenőrzés a `9c136cd` éles változaton indult, ismételt „No connected street
route” felhasználói hibajelzések után. A kezdőlap és az értelmezés válaszolt,
és egy közvetlen utcai útvonaljavítás is sikerült. Ez nem helyettesíti a teljes
generálási folyamat ellenőrzését; a korábbi kiadás éles próbájából ez kimaradt.

### Tartósan reprodukálható preferenciahiba

Az opcionális beállításokkal külön, ugyanazon szegedi négyzeten végzett éles
próbák a következőt mutatták:

| Mód és beállítás | Válasz |
| --- | --- |
| Futás, preferenciák nélkül | Utcai útvonal, HTTP 200 |
| Futás, lépcső/komp/gázló kerülése külön-külön | Utcai útvonal, HTTP 200 |
| Futás, csendesebb utak | HTTP 503 |
| Futás, zöldebb utak | HTTP 503 |
| Futás, az összes preferencia | HTTP 503 |
| Kerékpár, az összes preferencia | Utcai útvonal, HTTP 200 |

A közvetlen szolgáltatói hívás pontosította az okot: a program a futási
`quiet` és `green` súlyokat beágyazott `factor` objektumban küldte. Az éles
ORS 9.10.0 ezeket számmal fogadja; a régi struktúrára HTTP 400 / 2002 hibát
adott. A helyes számtípusú értékekkel ugyanaz a hívás HTTP 200 választ és
útvonalat adott, `shortest` és `recommended` alappreferenciával is.
A [verziózott kérésmodell](https://github.com/GIScience/openrouteservice/blob/v9.10.0/ors-api/src/main/java/org/heigit/ors/api/requests/routing/RequestProfileParamsWeightings.java)
szintén számtípusú mezőket határoz meg. Korábbi tesztünk és a dokumentációs
példánk a hibás struktúrát várta el; ezeket is javítottuk.

Bekapcsolva maradt csendes/zöld futási preferencia ezért új város vagy
alakzat választásakor is ismételt hibát okozhatott.

### Kommunikációs próbák preferenciák nélkül

Ugyanazon szegedi négyzetkérésnél az első, jóváhagyott értelmezéssel indított
streamelt generálás sikertelen volt: a preflight nem mért használható
elhelyezést, az első Directions-hívás után pedig nem volt utcai útvonal.
Változatlan kóddal később mind a négy változat adott szolgáltató által
útvonalazott eredményt:

| Válasz | Jóváhagyott értelmezés | Megismételt eredmény |
| --- | --- | --- |
| Normál JSON | Nincs | Utcai útvonal |
| Normál JSON | Van | Utcai útvonal |
| Streamelt | Nincs | Utcai útvonal |
| Streamelt | Van | Utcai útvonal |

Ez a preferenciák nélküli esetben időszakos szolgáltatói kommunikációs hibára
utal; az értelmezés és a streaming kombinációi később működtek. Az eredeti két felhasználói
korrelációs azonosító naplóit a rendelkezésre álló Northflank-kulcs nem
olvashatja: hiányzik a **Project → Services → Deployment → View Observability**
jogosultság. Az eredeti hibák pontos alacsony szintű oka ezért nem igazolt.

## Javítás

Az adapter közös kérésépítője most `quiet: 1.0` és `green: 0.8` értékeket küld
számként. Nem hagyja el a felhasználó preferenciáit, nem módosítja a kerülési
beállításokat, és megőrzi a konfigurált alap útvonalpreferenciát. A javítás
a generálásra, a kézi szerkesztésre és az alakfelismerési javításra is érvényes.

Az adapter korábban egyetlen Directions-olvasási időtúllépés után feladta az
útvonalat. Most egy ilyen időtúllépés ugyanazokkal a vezetőpontokkal,
sugárral és beállításokkal egyszer újrapróbálható. A próba a meglévő hét
szolgáltatói kísérlet egyikét használja; a határidő és a megszakítás továbbra is
érvényes. Második olvasási időtúllépésnél leáll. Kapcsolódási, írási,
kapcsolatkészlet-, hitelesítési és kvótahibák nem kapnak új próbákat.

Ha továbbra sincs valódi utcai geometria, az API nem ad GPS-fájlt. A meglévő
biztonságos hibaüzenet különbséget tesz a Directions-kapcsolati hiba,
elutasított útvonalbeállítás, kéréskorlát és hitelesítési konfiguráció között,
ha ehhez van mérési adat.
Nem tanácsol városváltást egy ismert szolgáltatói kapcsolat- vagy kvótahibára,
és nem tesz közzé nyers szolgáltatói választ vagy titkos adatot.

A hálózati naplóüzenet az exception típusát is rögzíti, mert egyes
időtúllépések szövege üres. A pontozás, az alakhűségi küszöbök, a
vezetőpont-felbontás és a visszaadott szolgáltatói geometria változatlan.

## Ellenőrzés és korlátok

- A regressziós teszt a javítás előtt két esetben elbukott: már az első
  időtúllépés után leállt.
- A számtípusú preferenciák hat szerződéstesztje a régi formátummal elbukott;
  a külön és együttes súlyokat mindkét alap útvonalpreferencián ellenőrizzük.
- Az érintett backend résztesztsorozat: **451 sikeres** teszt; Ruff és mypy
  sikeres, 71 alkalmazásmodullal.
- A végleges backend tesztsorozat: **995 sikeres** teszt, beleértve a
  változatlan vezetőpontokat, az egyszeri újrapróbálást, a teljes próbakeretet,
  a határidőt, a megszakítást és az újabb próbát nem kapó hibákat.
- Normál és streamelt API-hibatesztek ellenőrzik az okhoz illő üzenetet és a
  szolgáltatói részletek visszatartását.
- Azonos bemenetű pontozási audit: **1160 bitre azonos összehasonlítás**,
  145 sablon 580 geometriai párján; a védett minőségi és geometriai fájlok
  változatlanok.
- A valódi böngészős próba budapesti szívvel eljutott az eredményoldalig;
  a térképi útvonal 235 pontja megegyezett a GPX és a TCX tartalmával. Ez a
  preferenciák nélküli alapfolyamat ellenőrzése a javítás előtti változaton.
- Ugyanez a böngészős folyamat bekapcsolt csendes/zöld preferenciával a
  javítás előtti változaton a felhasználó által jelzett hibaképernyőre jutott.

A javítás átmeneti olvasási időtúllépésből tud helyreállni. Tartós szolgáltatói
kiesést, hibás kulcsot vagy elért kvótát nem szüntet meg. A sikeres éles
generálások nem jelentenek minden alakzatra kiterjedő minőségi vagy
késleltetési benchmarkot. A teljes kiadási CI és a javítás utáni éles próbák
eredményét a kiadási futáshoz kell kötni.

A mérési adatok és a hibás próbák is az ignorált
`test-results/generation-incident-2026-10-26/` könyvtárban maradnak.
