# GPS Art Wizard – javítási és regressziós tesztjelentés

**Dátum:** 2026-09-02
**Éles cél:** `https://p01--cityshaperunner--vnycn2g6bghl.code.run/`
**Vizsgált munkatér:** `C:\gpsArtWizzard`
**Módszer:** Playwright funkcionális és exploratív E2E, valós éles smoke/generálás, pytest, Ruff, mypy, Vite build, security-header és production-build böngészőteszt

## Vezetői összefoglaló

A korábbi audit minden igazolt alkalmazás- és toolinghiányossága javítva lett. A helyi kiadási jelölt **GO** minősítésű: a backend 600/600 tesztje, a frontend unit tesztek, a build, a lint és a típusellenőrzés hibátlan; Chromium desktopon és mobilon minden funkció igazolt, WebKit alatt 114/114 eset átment. A korábbi Firefox `newPage` blocker megszűnt a Playwright és a hozzá tartozó böngészőverzió frissítésével.

Az éles domain most ebből a környezetből is elérhető. A health és gallery API, a galérianavigáció/lightbox, valamint egy valódi, közzététel nélküli útvonal-generálás sikeres volt. Az éles példány a régi kiadást futtatja: HSTS-t ad, CSP-t még nem. Az új biztonsági middleware csak a módosítások kiadása után jelenik meg az éles válaszokon.

## Tesztmátrix

| Terület | Eredmény | Megjegyzés |
|---|---:|---|
| Backend pytest | **600/600 sikeres** | Figyelmeztetés nélkül, projektbe rögzített `.pytest-tmp` basetemppel |
| Ruff | **sikeres** | `All checks passed!` |
| Mypy | **sikeres** | 62 forrásfájl, 0 hiba |
| Frontend unit | **10/10 sikeres** | Setup-payload és normalizálási szerződések |
| Vite production build | **sikeres** | Optimalizált bundle elkészült |
| Chromium desktop | **114/114 igazolt** | A teljes desktop projekt elsőre átment |
| Chromium mobil | **114/114 igazolt** | 113 elsőre; 1 Windows socket-erőforráshiba után izoláltan sikeres |
| Firefox | **114 funkció igazolt** | 113 első teljes körben; az egy szerkesztési state-teszt javítás után 5/5 ismétlésben sikeres |
| WebKit | **114/114 sikeres** | Teljes, tiszta futás |
| Éles API + galéria UI | **2/2 sikeres** | `/health`, `/gallery`, Gallery navigáció, lightbox és teljes kép |
| Éles route quality E2E | **1/1 sikeres** | Valós prompt, `/generate`, routing, minőségi kapu, térkép és tile-ok; publikálás nélkül |
| Security-header contract | **sikeres** | Automatikus backend teszt és valódi production-build böngészőteszt |
| NPM audit | **0 ismert sérülékenység** | A Playwright-frissítés után |

## Éles környezet igazolása

Közvetlen HTTP-ellenőrzés:

| Végpont | HTTP | Tartalom |
|---|---:|---|
| `/` | 200 | SPA HTML |
| `/health` | 200 | `status: ok`, galéria konfigurálva |
| `/gallery` | 200 | Cloudinary assetlista |

A Playwright éles galériateszt a fejléc **Gallery** linkjén keresztül nyitotta meg a `#gallery` nézetet, megnyitotta az első képet lightboxban, és igazolta a teljes, levágás nélküli `object-fit: contain` megjelenítést.

A valós generálási teszt publikálás nélkül futott. A debreceni első próbálkozást a rendszer helyesen elutasította az overall score, detour control és distance fit küszöbök miatt. A barcelonai jelölt automatikusan ellenőrzött és elfogadott lett:

- overall score: **0,7823**;
- shape fidelity: **0,8932**;
- spatial similarity: **0,8952**;
- coverage: **0,9364**;
- turning similarity: **0,7511**;
- landmark similarity: **0,9934**;
- reversal similarity: **1,0000**;
- proportions: **0,9745**.

Az éles galériába nem került tesztbejegyzés. A publikálás és törlés teljes szerződése a determinisztikus E2E- és backendtesztekben lefedett, de a nyilvános Cloudinary-állapotot ez a kör szándékosan nem módosította.

## Javított megállapítások

### QA-01 – Mobil találati szövegek túl kicsik

**Korábbi súlyosság:** P2
**Állapot:** javítva és automatizáltan védve

A döntési, mérőszám-, readiness-, route-detail- és GPX-segédszövegek kompakt nézetben legalább 12 px számított betűméretet kapnak. Az új Playwright-regresszió a kritikus selectorok minimumát tényleges `getComputedStyle()` értékből méri.

### QA-02 – Túl hosszú mobil találati út az exportig

**Korábbi súlyosság:** P3
**Állapot:** javítva

A mobil eredményfejléc új **Download options ↓** gyorslinket kapott. A link a `#route-download` kártyára görget, megőrzi a biztonságos információs sorrendet, desktopon pedig rejtve marad. A hash-váltást és a cél viewportba kerülését külön E2E teszt ellenőrzi.

### QA-INFRA-01 – Playwright nem áll le a tesztek végén

**Korábbi súlyosság:** P2
**Állapot:** javítva

A Playwright 1.61.1-ről pontosan rögzített 1.62.1-re frissült, és a Chromium/Firefox/WebKit binárisok a hozzá tartozó revisionre lettek újratelepítve. A célzott, éles és teljes futások most önállóan visszaadják az exit státuszt; kézi processleállítás nem kellett.

### QA-INFRA-02 – Firefox `browserContext.newPage` összeomlás

**Korábbi súlyosság:** P2
**Állapot:** javítva

A verziópáros frissítése után Firefox oldalt nyit, és a teljes projekt lefut. Egy ritka szerkesztési pointer/state időzítési flake jelent meg; az érintett state-teszt billentyűzetes aktiválással most az API utáni állapotot izoláltan méri, és 5/5 ismétlésben átment. A pointeres útvonalszerkesztést több más teszt változatlanul lefedi.

### QA-INFRA-03 – WebKit intermittáló timeoutok

**Korábbi súlyosság:** P3
**Állapot:** jelen körben nem reprodukálható

Az új Playwright/browser revisionnel a teljes WebKit projekt 114/114 eredménnyel, retry nélkül zárult.

### QA-INFRA-04 – Mypy hiányzó típusinformációk

**Korábbi súlyosság:** P3
**Állapot:** javítva

A dev függőségek közé bekerült a verziórögzített `types-PyYAML` és `types-Shapely`; a stub nélküli `svgelements` célzott, szűk mypy override-ot kapott. Eredmény: 0 hiba 62 fájlban.

### QA-INFRA-05 – Starlette TestClient deprecáció

**Korábbi súlyosság:** P3
**Állapot:** javítva

A Starlette által támogatott `httpx2` bekerült a dev függőségek közé. A teljes 600-as pytest futás figyelmeztetés nélkül zárult.

### QA-SEC-01 – Hiányzó alkalmazásoldali security headerek

**Korábbi súlyosság:** P3 hardening
**Állapot:** helyben javítva; élesítésre vár

Központi FastAPI middleware állítja be:

- `Content-Security-Policy` szűk, az OSM tile és Cloudinary képekhez szükséges kivételekkel;
- `Permissions-Policy`;
- `Referrer-Policy: strict-origin-when-cross-origin`;
- `Strict-Transport-Security`;
- `X-Content-Type-Options: nosniff`;
- `X-Frame-Options: DENY`.

A buildet a FastAPI-n át betöltő Chromium-tesztben a React alkalmazás és a galéria működött, 0 konzolhibával és 0 sikertelen erőforráskéréssel. A jelenlegi éles kiadásban CSP még nincs, ezért ezt a kiadás utáni smoke tesztben újra kell ellenőrizni.

### QA-TEST-01 – Elavult produkciós Playwright-folyamatok

**Súlyosság:** P2 tesztmegbízhatóság
**Állapot:** javítva

Két teszthiba nem termékhiba volt:

- a galéria tesztje a planner nézeten keresett `.gallery-card` elemet; most a felhasználói **Gallery** linkkel vált nézetet;
- a generálási helper kihagyta a **Review request** lépést; most a tényleges kétlépcsős folyamatot járja végig.

Mindkét javítás éles domainen is sikeresen lefutott.

## Funkcionális lefedettség

Igazolt fő területek:

- szabad prompt, gyors ötletek, 158 elemű forma-/betű-/számkatalógus;
- magyar, európai és Balaton-parti helyek, ékezetes nevek;
- futás/kerékpár, távolsági határok, cím, GPS, kezdőirány és útpreferenciák;
- forma pozicionálása, méretezése és forgatása, kép-URL alapú indítás;
- review lépés, generálás, megszakítás, retry és elavult válasz elleni védelem;
- alternatívák, minőségi gate-ek, route readiness, weather, night, accessibility és sightseeing rétegek;
- térkép forgatás, billentyűzetes és pointeres útvonalszerkesztés;
- GPX/TCX export, biztonságos fájlnév, félkész szerkesztés alatti exporttiltás;
- gallery empty/error/unconfigured állapot, lightbox, billentyűzet, lapozás, lazy loading;
- hozzájárulás, anonim publikálási payload, capability-tokenes eltávolítás és hibakezelés;
- Inkproof, Missing Ink, mural, worksheet, poster, reel és kampánylink;
- SEO fallback, robots/sitemap, reduced motion, fókuszkezelés, 44 px érintési célok és vízszintes overflow hiánya.

## Teljesítmény és build

A Vite production build sikeres. A fő gzip méretek:

- alkalmazás JS: **101,39 kB**;
- CSS: **28,72 kB**;
- Leaflet lazy chunk: **44,58 kB**;
- RouteMap lazy chunk: **4,74 kB**;
- ShapePlacementMap lazy chunk: **1,62 kB**.

## Maradék kockázatok

- Egy 7 perces, 228 esetes Windows Chromium-futásban egyszer `ERR_NO_BUFFER_SPACE` jelent meg az új oldal hálózati megnyitásakor. Az érintett teszt tiszta folyamatban azonnal átment. Ez runner/socket-erőforrás-kockázat, nem alkalmazási assertion-hiba; a CI Linuxon fut és projektenként retry-t is használ.
- A security-header javítás és a mobil UX-javítás jelenleg a `codex/integrate-route-setup` munkafán van, nem az éles kiadásban.
- Külső Garmin/Strava/Komoot import nem automatizálható felhasználói fiókok nélkül; a generált formátumokat és letöltéseket helyi szerződés- és E2E-tesztek ellenőrzik.

## Kiadási javaslat

**GO a minőségi kapun keresztüli kiadásra.** A módosítások masterre juttatása után a dokumentált GitHub Actions → Northflank exact-SHA folyamatot kell használni. Kiadás után kötelező rövid smoke:

1. `/`, `/health`, `/gallery` továbbra is 200;
2. az éles válasz már tartalmaz CSP-t és a többi alkalmazásoldali fejlécet;
3. mobil eredménynézeten a 12 px minimum és a Download options link jelen van;
4. egy route generation és egy gallery lightbox megnyitás sikeres.
