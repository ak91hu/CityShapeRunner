# Paceasso — használhatósági vizsgálat, 2026-10-19

## Módszer és hatókör

A vizsgálat szakértői feladatbejárást, elsődleges UX- és akadálymentességi
források áttekintését, működő böngészőben végzett ellenőrzést és javítást foglal
magában. Nem résztvevőkkel végzett felhasználói kutatás: nincs mért emberi
feladatidő, SUS-pontszám, elégedettségi vagy felismerési arány.

A fő feladatok: ötlet megadása; példa, alakzatjavaslat, térképi elhelyezés vagy
képhivatkozás választása; a kérés ellenőrzése és javítása; várakozás és
megszakítás; útvonalak összehasonlítása; szerkesztés; ellenőrzött vagy külön
jóváhagyott letöltés; visszatérés a galériából és a böngésző előzményeiből.
A galéria és a kiegészítő eszközök is részei az ellenőrzésnek.

## Kutatási alap → tervezési döntés

| Elsődleges forrás | Az alkalmazásban követett döntés |
|---|---|
| [Nielsen: 10 használhatósági heurisztika](https://www.nngroup.com/articles/ten-usability-heuristics/) | Felismerhető következő lépés, következetes állapotok, javítható hibák, visszalépés és megszakítás. |
| [NN/G: Progressive Disclosure](https://www.nngroup.com/articles/progressive-disclosure/) | A fő kérés és továbbgomb megelőzi az opcionális mintákat és eszközöket; az összetett beállítások külön nyithatók. |
| [NN/G: Website Forms Usability](https://www.nngroup.com/articles/web-form-design/) | Kapcsolódó mezők együtt, egyértelmű címkék, a bevitelt közvetlenül követő művelet. |
| [GOV.UK: Check answers](https://design-system.service.gov.uk/patterns/check-answers/) | A generálás előtt külön ellenőrző lépés és közvetlen javítási út. |
| [GOV.UK: Validation](https://design-system.service.gov.uk/patterns/validation/) | Mezőhöz kapcsolt, javítást segítő hiba; az adat és az útvonalötlet megőrzése. |
| [WCAG 2.2: Reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html) | A teljes oldal 320 CSS-pixelen sem igényel oldalirányú görgetést. A térkép belső kétdimenziós kezelése külön kérdés. |
| [WCAG 2.2: Contrast Minimum](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) | A normál szöveg célértéke legalább 4,5:1; a mért, küszöb alatti színeket sötétítjük. |
| [WCAG 2.2: Target Size Minimum](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html) | Az AA-minimum 24 CSS-pixel, meghatározott kivételekkel. A fő saját műveleteknél a projekt 44 pixeles méretet használ. |
| [WAI APG: Modal Dialog](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/) | Értelmes kezdőfókusz, látható vezérlők közötti Tab-kör, inaktív háttér, Escape, fókusz-visszaadás. |
| [WCAG: Status Messages](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html) | A folyamat állapota és a hibajavítási visszajelzés programozottan is elérhető. |
| [NN/G: Response Time Limits](https://www.nngroup.com/articles/response-times-3-important-limits/) | Hosszú művelet közben tényleges munkafázis, eltelt idő és megszakítás; bizonytalan futásra nem adunk kitalált százalékot. |

## Megállapítások és megvalósított javítások

A súlyosság szakértői prioritás, nem résztvevőkön mért gyakoriság.

| Prioritás | Megfigyelt probléma | Javítás és bizonyíték |
|---|---|---|
| Magas | 320 px szélességnél az eredményoldal 28 pixellel kilógott. | A megmaradt asztali, minimum 20 rem széles második grid-oszlop helyett kompakt nézetben valódi egyoszlopos grid. Méretmérés és képernyőkép. |
| Magas | Mobilon az alternatív útvonalak oldalirányú listában, részben a képernyőn kívül voltak. | Egymás alatti, teljes szélességű kártyák, tördelődő státuszcímkék. A kiválasztott állapot szöveggel és szegéllyel is látható. |
| Magas | A jelöltgombok `listitem` szerepe felülírta a gomb szemantikáját; az `aria-pressed` így érvénytelen volt. | Valódi listaelemen belüli valódi gomb; a kiválasztás továbbra is billentyűzettel kezelhető. Axe és billentyűzetes teszt. |
| Magas | A mobilos várakozás lezárta a görgetést, de nem kezelte teljesen a háttérfókuszt és az elforgatást. | Kompakt nézetben valódi modális állapot, inaktív háttér; a méretváltásra a görgetészár és a szemantika is frissül. |
| Magas | Gyors billentyűzetes továbblépésnél a mobilos WebKit néha visszafókuszált az ötletmezőre. | A StrictMode azonos DOM-elemre ismételt ref-csatolása csak egyszer ad kezdőfókuszt; nyolc külön gyors Tab-próba és az ismételt böngészős ellenőrzés. |
| Magas | A Vite alapkonfigurációja több API-végpontot nem továbbított. A `/shape-templates` például JSON helyett HTML-t adott. | Minden kliens-API-erőforrás a backendhez kerül. A teszt a tényleges `api.js` hívások lefedését ellenőrzi; élő próba is készült. |
| Közepes | Több kiegészítő felirat kontrasztja 4,46:1, a kijelölt kártyán 4,28:1 volt. | Sötétebb másodlagos szövegszín; az alkalomajánló hangsúlyszíne is javítva. Nincsenek kikapcsolt axe-szabályok. |
| Közepes | Az eredmény-, galéria- és várakozó nézetnek nem volt saját első szintű címe. | Állapotonként megfelelő H1 és hozzá kapcsolt régió-/dialóguscím; a meglévő vizuális hierarchia megtartásával. |
| Közepes | A márkalink felolvasott neve nem tartalmazta a teljes látható nevet. | Teljes, a látható szöveghez illeszkedő név és egyértelmű szóköz a márka és alcím között. |
| Közepes | Az opcionális minták és katalógus a fő továbbgomb előtt kerültek a tabulátorsorrendbe. | A szövegmező után közvetlenül a „Review request” következik, a példák ezután érhetők el. |
| Közepes | A példa kiválasztása nemcsak az alakzatot, hanem a várost, tevékenységet és távot is módosította, de ezt a címke nem mondta el. | „Example requests”, magyarázó szöveg és visszafókusz az új mondatra, ahol rögtön javítható. |
| Közepes | Az alternatív belépők neve nem jelezte pontosan a működést. | „Suggest a shape”, „Place on map”, „Use image link”; a képlink súgója a használható bemenetre koncentrál. |
| Közepes | Az értelmezési kérés közben újra megnyomható volt a küldőgomb. | A folyamatot jelző gomb átmenetileg letiltott; a sikeres válasz után a következő művelet használható. |
| Közepes | A modális fókuszlista elrejtett vezérlőket is tartalmazhatott; a natív összecsukók kimaradtak. | Csak látható, tabulátorral elérhető vezérlők; a `summary` elemek is a kör részei. A galéria háttere is inaktív a képnézőben. |
| Alacsony | A szezonális ötletek `details` elemének `region` szerepe nem volt megfelelő. | Címkézett szakaszon belüli natív összecsukó. |

A Safari egyik teljes futásában az opcionális panel kattintás után zárva maradt.
Tíz elkülönített, trace-szel rögzített ismétlés sikerült, ezért az okát nem
tekintjük bizonyítottnak. Egy kapcsolódó időzítési kockázatot javítottunk: az
eredményre és várakozásra ugrás most `instant`, mert az `auto` örökölte az oldal
sima görgetését. Az állapotváltás elavult fókusz-frame-je megszakítható. A
tesztsegédek a natív `open` állapotot ellenőrzik, nem egy leszármazott
láthatóságából következtetnek rá. Az eredeti sikertelen futásokat is megőrizzük.

## Bizonyíték és ellenőrzési mátrix

- Összehasonlítható képernyőminták: 1440, 390 és 320 CSS-pixel; mindegyiknél
  kezdőlap, külön mezők, kérésellenőrzés, eredmény, felülvizsgálandó jelölt és
  dialógus. Összesen 18 állapot-/méretkombináció verziónként.
- A kezdő auditban 5 különböző axe-szabályhoz tartoztak hibák. Az ismétlődő
  nézeteket is számítva 52 szabálysértés-megfigyelés, 99 érintett elem-megfigyelés
  szerepel; ezek nem 99 különálló termékhibát jelentenek.
- A javított 18 állapotban nulla automatikusan jelzett szabálysértés és nulla
  teljes oldali vízszintes kilógás. A nyers audit a nem eldönthető
  (`incomplete`) eredményeket is megőrzi.
- Kiegészítő böngészős ellenőrzés: 320×568, 390×844, 768×1024, 844×390,
  1024×768 és 1440×900; továbbá 200%-os gyökér-betűméret 1280 pixeles ablakban.
  Ez utóbbi nem helyettesíti minden böngésző saját nagyítási módjának tesztjét.
- Motorok és eszközprofilok: asztali és Android-emulált Chromium; asztali
  Firefox; asztali és iPhone-emulált WebKit. Az emuláció nem fizikai készülékteszt.
- A fő művelet egy Tab-lépésre került a szövegmezőtől. A konkrét kezdő mintában
  a továbbgomb helye 390 pixeles szélességnél 1218,6-ról 930,5 dokumentumpixelre
  került; ez elrendezési adat, nem felhasználói időnyereség.
- Élő integrációs próba a buildelt, FastAPI által kiszolgált alkalmazással:
  145 sablon betöltése és a kérés ellenőrzése 1440 és 390 pixelen. Nem indult
  útvonalgenerálás vagy nyilvános megosztás. A működő fejlesztői proxyt külön
  JSON-válaszokkal is ellenőriztük.

Az automatizált feladatok ellenőrzik az érvénytelen bemenet javítását,
az egyszeri kérésküldést, a példák kiválasztását, a felülvizsgálandó jelöltet,
a fókuszkört és fókusz-visszaadást, az orientációváltást, a görgetés feloldását,
valamint a korábbi teljes tervező-, szerkesztő-, galéria- és exportfolyamatokat.
A tesztadatokkal végzett megosztás nem tesz közzé valódi felhasználói adatot.

A végleges futási eredmények és a forrásfájlok SHA-256 azonosítói a helyben
generált `test-results/ui-usability-2026-10-19/` bizonyítékcsomagban szerepelnek.
Az eredeti két teljes futás 294 Chromium- és 126 további böngészős esetből állt.
A közben talált hibákat célzott újrafuttatások követik; az összesített eredmény
projektenként, fájlnév és tesztcím alapján a legutóbbi eredményt veszi figyelembe.
Ez nem egyetlen teljes futás a végső forráson. A nyers JSON-ok minden kezdeti
hibát is megőriznek. A végső célzott kör 32 Chromium- és 48 Firefox/WebKit-esetet
ellenőriz; külön 14 egységteszt és a termelési build is sikeres.

A hordozható, képernyőválasztós összehasonlító jelentés újragenerálása:

```powershell
python scripts/render_ui_usability_report.py
```

A jelentéskészítő megáll, ha az auditált forrás azóta változott, a 18 nézet
hiányos, vagy bármely megőrzött teszteset legutóbbi eredménye sikertelen.
A ZIP a nyers bizonyítékokat és a vizsgált forrásokat is tartalmazza, fájlonkénti
SHA-256 manifesttel. A kiinduló állapothoz az eredeti audit és képek maradtak
meg; teljes, befagyasztott kiinduló forrásmásolat nincs.

## Újrafuttatás

```powershell
cd frontend
npm ci
npm run test:unit
npm run test:e2e
npm run test:cross-browser -- accessibility-functional.spec.js usability-functional.spec.js generation-experience.spec.js extras-functional.spec.js gallery-resilience-functional.spec.js
npm run build
```

A képernyőaudithoz külön Vite-szerver használható 4175-ös porton:

```powershell
node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 4175
# Másik terminálban:
node scripts/audit-usability.mjs ../test-results/ui-usability-2026-10-19/after-final
```

Az élő próba a már futó helyi backenddel végezhető:

```powershell
node scripts/smoke-usability.mjs http://127.0.0.1:8000 ../test-results/ui-usability-2026-10-19/live-production
```

## Az eredmények értelmezése

A zöld automatizált ellenőrzés nem WCAG-megfelelőségi tanúsítvány. Nem végeztünk
NVDA-/VoiceOver-próbát, fizikai telefonos terepi tesztet vagy résztvevői kutatást.
Az auditált állapotokat az útvonalminőségi backendtől külön, szabályozott API- és
térképcsempe-válaszokkal ellenőriztük; a képernyőpéldák nem GPS-art-minőségi mérések.
Az élő integrációs próba ennek külön kiegészítése.

Következő felhasználói vizsgálatként érdemes kezdő és tapasztalt futókkal,
valamint kerékpárosokkal elvégeztetni a saját város és alakzat megadását,
a félreértett kérés javítását, egy gyengébb jelölt felismerését és a GPX mentését.
Megfigyelendő: segítség nélküli befejezés, hibák, javítási út, a várakozás
értelmezése és az, hogy a felhasználó megkülönbözteti-e az automatikus
ellenőrzést a saját jóváhagyásától. Ez javasolt későbbi kutatás, nem már elvégzett mérés.
