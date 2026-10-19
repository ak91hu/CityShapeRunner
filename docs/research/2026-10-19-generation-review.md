# GPS-art generálás: kutatási és kódellenőrzés

Dátum: 2026-10-19. A vizsgálat az aktuális munkapéldányt ellenőrzi; az élő
mérések eredményeit a [mérési jelentés](../reports/2026-10-19-creative-fit.md)
tartalmazza. A szakirodalmi eredmények nem az alkalmazás saját mérési eredményei.

## Kutatási alap

| Elsődleges forrás | A feladathoz kapcsolódó megállapítás | Következmény az alkalmazásban |
| --- | --- | --- |
| [Waschk–Krüger, 2019: Automatic route planning for GPS art generation](https://duepublico2.uni-due.de/servlets/MCRFileNodeServlet/duepublico_derivate_00072443/Waschk_et_al_Automatic_Route_Planning.pdf), 4., 6–8. fejezet | A legrövidebb út és a legközelebbi utcára vetítés önmagában elveszítheti a rajz részleteit. A gráfköltségnek a kontúrtól való eltérést is értékelnie kell. A ritka úthálózat és az apró részletek alapvető korlátok. | Helyes az alakzatot követő gráfjavaslat és a végső utcai geometria külön pontozása. Több vezérpont vagy egy jobb Snap-pontszám nem bizonyít jobb GPS-artot. |
| [Powałka, 2023: Shape-guided artistic route finding](https://repository.tudelft.nl/record/uuid:11e9b0c2-5d67-475a-8653-71c7afe03dad), egyetemi dolgozat összefoglalója | A helykeresés, az alakzatra szabott gráfköltség és több jelölt értékelése külön feladat; az interaktív mozgatás, forgatás és méretezés is része lehet a folyamatnak. | Indokolt a város több térségének, eltérő forgatásainak és méreteinek vizsgálata. A kézzel megadott helyet és indulási megkötéseket meg kell őrizni. |
| [Yao–Bekhor, 2020: Experiments on route choice set generation using a large GPS trajectory set](https://arxiv.org/abs/2006.04536) | A különböző alternatívaképző eljárások eltérő átfedésű és változatosságú útvonalkészleteket eredményeznek. Az élkizárás megszakíthatja a hálózatot. | A változatosságot térbeli távolsággal és a kész útvonalak átfedésével kell ellenőrizni. Az utak törlése a gráfból veszélyes eszköz lenne a változatosság erőltetésére. Ez útvonalválasztási kutatás, nem GPS-art minőségi validáció. |
| [ORS Snap dokumentáció](https://giscience.github.io/openrouteservice/api-reference/endpoints/snapping/) és [nyilvános API-korlátok](https://openrouteservice.org/restrictions/) | A Snap a legközelebbi élt adja vissza; a sugáron belüli találat hiányát `null` jelzi. A közzétett korlát 5000 Snap-hely és 50 Directions-vezérpont kérésenként. | A kötegelt Snap olcsó előszűrés, nem összefüggő útvonal. A végső útvonalhoz külön Directions-válasz kell. A kliens 5000 és 50 pontos korlátai megfelelnek az ellenőrzött dokumentációnak. |

## A tényleges folyamat ellenőrzése

Az API az orchestratornak adja a kérést és az opcionális `search_seed` értéket.
Ennek hiányában minden futás új magot kap. A PreflightAgent megtartja a korábbi
keresési családot, és külön, maggal reprodukálható mintákat vesz a város 16
térségéből. Teljes körű forgatást és három méretet is vizsgál. Az adaptív
előszűrés három mért körben szűkíti a keresést. A két család közös Snap-kérésekben
utazik; a normál keret 180 régi és legfeljebb 90 új elhelyezés.

A lokális gráf a kapcsolódási és kitérési kockázat becslésében segít. A teljes
útvonalmérés legfeljebb három kezdeti elhelyezést futtat a korlátozott
workerszámmal. A szolgáltató által visszaadott utcai pontok mennek át az alak-,
távolság-, záródás- és kapcsolódási ellenőrzésen. Az elfogadási kapukat és a
pontozás felbontását ez a javítás nem változtatja meg.

Az eredeti keresési család teljes shortlistje megmarad. A legjobb mért útvonal
választása továbbra is a közös minőségi rangsorral történik, a javítások rosszabb
eredmény esetén visszaállnak. A közeli, azonos Directions-kérések futáson belüli
gyorsítótárat használnak, pontos koordinátakulccsal. Eltérő elhelyezést nem szabad
egy kerekített kulccsal azonosnak tekinteni.

## Talált és javított hiányosság

A kreatív család második jelöltje csak a saját családja első jelöltjétől kellett
eltérjen. Így visszatérhetett a régi család már kiválasztott környékére. A
shortlist most mindkét első jelölthöz viszonyítja a szabad hely térbeli
változatosságát. Megmarad a legerősebb kreatív proxy és az egész régi shortlist;
nem nő a kezdeti teljes útvonalmérések száma.

A távolabbi jelölt csak az előszűrés meglévő összehasonlíthatósági feltételével
kaphat elsőbbséget: pontszáma legalább `max(0.35, 0.8 × első kreatív pontszám)`.
Ez keresési heurisztika, nem a kész útvonal elfogadási küszöbe. Gyenge távoli
jelölt kedvéért a shortlist nem kényszerít új környéket. A végső minőséget továbbra
is a valódi útvonalon kell mérni.

## Hatékonyság és fennmaradó korlátok

Az új mag különböző keresési helyeket ad, de önmagában nem bizonyít különböző
végeredményt. Az API az első ajánlást a minőségi rangsor szerint tartja meg;
a kártyák változatos rendezése sem változtatja meg az első ajánlást. Ha ugyanaz
az útvonal marad a legjobb mért megoldás, a rendszer ezt megtarthatja. Másik
környék mindenáron történő előírása és a minőség feltétlen megőrzése nem
garantálható tetszőleges város–alakzat párosra.

A felhasználó választott szabálya szerint a legpontosabb ajánlás megmarad;
a választható alternatíváknál kell törekedni a változatos környékekre. A
shortlist javítása ezt a szabályt követi, a végső minőségi rangsort megőrzi.

A 35 másodperces feltárási keret az új, opcionális méréseket korlátozza. A
kötelező ellenőrzések és a minőséghez szükséges javítások a 175 másodperces
alapkeretet használják; a futó hálózati hívás befejeződhet. Emiatt ez nem kemény
válaszidő-garancia. A párhuzamosítás egy futáson belül korlátozott; sok egyidejű
felhasználó közös szolgáltatói kvótája külön üzemeltetési kapacitáskorlát.

A Dockerfile és a telepítési leírás külön 256 MB-os profilt tartalmaz:
90 régi elhelyezés, 4 elemű shortlist, 75 másodperc, 2 finomítás, kikapcsolt
helyi gráf és végső polírozás. Ez kevesebb keresési lehetőség, mint az alapbeállítás.
Azonos minőségi kapu nem bizonyít azonos találati minőséget vagy sikerarányt.
A helyi gráf visszakapcsolása ezen a kis memóriájú gépen sem tekinthető igazolt
javításnak. A mostani élő alapkonfigurációs mérés nem ennek a konténerprofilnak
a validálása; a két környezetet nem szabad összemosni.
