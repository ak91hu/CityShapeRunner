# Útvonaltervezési hibák vizsgálata — 2026. október 27.

## Megfigyelések

Az ellenőrzés a `9c136cd` éles változaton indult, ismételt „No connected street
route” felhasználói hibajelzések után. A kezdőlap és az értelmezés válaszolt,
és egy közvetlen utcai útvonaljavítás is sikerült. Ez nem helyettesíti a teljes
generálási folyamat ellenőrzését; a korábbi kiadás éles próbájából ez kimaradt.

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

Ez időszakos szolgáltatói kommunikációs hibára utal, önmagában nem bizonyít
állandó értelmezési vagy streaminghibát. Az eredeti két felhasználói
korrelációs azonosító naplóit a rendelkezésre álló Northflank-kulcs nem
olvashatja: hiányzik a **Project → Services → Deployment → View Observability**
jogosultság. Az eredeti hibák pontos alacsony szintű oka ezért nem igazolt.

## Javítás

Az adapter korábban egyetlen Directions-olvasási időtúllépés után feladta az
útvonalat. Most egy ilyen időtúllépés ugyanazokkal a vezetőpontokkal,
sugárral és beállításokkal egyszer újrapróbálható. A próba a meglévő hét
szolgáltatói kísérlet egyikét használja; a határidő és a megszakítás továbbra is
érvényes. Második olvasási időtúllépésnél leáll. Kapcsolódási, írási,
kapcsolatkészlet-, hitelesítési és kvótahibák nem kapnak új próbákat.

Ha továbbra sincs valódi utcai geometria, az API nem ad GPS-fájlt. A meglévő
biztonságos hibaüzenet különbséget tesz a Directions-kapcsolati hiba,
kéréskorlát és hitelesítési konfiguráció között, ha ehhez van mérési adat.
Nem tanácsol városváltást egy ismert szolgáltatói kapcsolat- vagy kvótahibára,
és nem tesz közzé nyers szolgáltatói választ vagy titkos adatot.

A hálózati naplóüzenet az exception típusát is rögzíti, mert egyes
időtúllépések szövege üres. A pontozás, az alakhűségi küszöbök, a
vezetőpont-felbontás és a visszaadott szolgáltatói geometria változatlan.

## Ellenőrzés és korlátok

- A regressziós teszt a javítás előtt két esetben elbukott: már az első
  időtúllépés után leállt.
- Az érintett backend résztesztsorozat: **445 sikeres** teszt; Ruff és mypy
  sikeres, 71 alkalmazásmodullal.
- A végleges backend tesztsorozat: **987 sikeres** teszt, beleértve a
  változatlan vezetőpontokat, az egyszeri újrapróbálást, a teljes próbakeretet,
  a határidőt, a megszakítást és az újabb próbát nem kapó hibákat.
- Normál és streamelt API-hibatesztek ellenőrzik az okhoz illő üzenetet és a
  szolgáltatói részletek visszatartását.
- Azonos bemenetű pontozási audit: **1160 bitre azonos összehasonlítás**,
  145 sablon 580 geometriai párján; a védett minőségi és geometriai fájlok
  változatlanok.

A javítás átmeneti olvasási időtúllépésből tud helyreállni. Tartós szolgáltatói
kiesést, hibás kulcsot vagy elért kvótát nem szüntet meg. A sikeres éles
generálások nem jelentenek minden alakzatra kiterjedő minőségi vagy
késleltetési benchmarkot. A teljes kiadási CI és a javítás utáni éles próbák
eredményét a kiadási futáshoz kell kötni.

A mérési adatok és a hibás próbák is az ignorált
`test-results/generation-incident-2026-10-26/` könyvtárban maradnak.
