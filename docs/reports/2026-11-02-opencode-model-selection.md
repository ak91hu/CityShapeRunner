# OpenCode modellválasztás — 2026-11-02

A kiválasztott modell **GPT-6 Luna**, az OpenCode fizetős, távoli API-ján.
A felhasználói döntés szerint a látogatók fele ezt, fele a Groq
`openai/gpt-oss-120b` modelljét kapja első szolgáltatóként. A besorolás anonim
böngészős cookie alapján stabil; nem jelent pontosan fele-fele API-hívásszámot.

## Ár és alkalmasság

Az árak USD / egymillió token, rövid kontextus és normál online hívás mellett.
A cache-olvasás és -írás külön díjtétel lehet.

| Modell az OpenCode-on | Bemenet | Kimenet | Értékelés ehhez a feladathoz |
| --- | ---: | ---: | --- |
| GPT-6 Luna | 0,10 | 0,50 | Kiválasztva; szigorú séma, képes bemenet, meglévő Responses adapter |
| GLM 5.3 Flash | 0,15 | 0,50 | Olcsó alternatíva; a valódi ShapeSpec-próba sikerült |
| Qwen3.8 Flash | 0,15 | 0,47 | Hasonló ár; ebben a vizsgálatban nem kapott élő rajzpróbát |
| GPT-5.4 Nano | 0,20 | 1,25 | Drágább és az OpenAI már elavultként (deprecated) jelöli; nem választottuk |
| GPT-5.4 Mini | 0,75 | 4,50 | Korábbi strukturált modell; magasabb tokenár |
| MiniMax M3 | 0,30 | 1,20 | Magasabb tokenár; nem kapott élő rajzpróbát |

Forrás: [OpenCode modellkatalógus és árlista](https://opencode.ai/v2/docs/console/models/),
a nyilvános OpenCode `/inference/v1/models` metaadatok,
[GPT-6 Luna hivatalos adatlap](https://developers.openai.com/api/docs/models/gpt-6-luna)
és [GPT-5.4 Nano hivatalos adatlap](https://developers.openai.com/api/docs/models/gpt-5.4-nano).
A Luna alkalmazásszintű alkalmassága következtetés a dokumentált képességekből
és a lenti szűk próbából; nem teljes GPS-art minőségi mérés.

Példa cache nélkül: 10 000 bemeneti és 4 000 kimeneti token Luna listaáron
0,003 USD; ez számítás, nem mért teljes generálási számla. Javítás, újrapróbálás,
cache-írás és a Groq hívásai külön változtathatják a végösszeget.

## Élő, azonos bemenetű ShapeSpec-próba

Mindkét modell ugyanazt az alkalmazásból betöltött rendszerpromptot, az
„a robot waving with its left arm” kérést és a valódi `_SHAPE_SPEC_JSON_SCHEMA`
sémát kapta az OpenCode Responses végpontján, 6144 kimeneti tokenes korláttal.
A Luna `reasoning.effort=low` beállítást kapott; a GLM a szolgáltatói alapértéket.

| Modell | HTTP / állapot | Alkalmazás-parser | Felismerési jellemzők | API által közölt díj |
| --- | --- | --- | ---: | ---: |
| GPT-6 Luna | 200 / completed | érvényes ShapeSpec | 5 | 0,0004858 USD |
| GLM 5.3 Flash | 200 / completed | érvényes ShapeSpec | 6 | 0,00061945 USD |

A teljes bemenet hash-e mindkét próbában azonos. A tokenek és a cache-elszámolás
eltértek; a táblázat egy-egy hívás számlázási visszajelzése, nem általános
költségelőny. A nyers, titkot nem tartalmazó eredmény helye:
`test-results/opencode-model-research/shape-spec-probes.json` (ignorált bizonyíték).

## Beállítás és korlátok

Az alkalmazás teljes rajzfázisával két további Luna-próba is lefutott:

| Meglévő benchmarkeset | Forrás | Modellhívás | Összefüggő rajzvonal | Pontok | Állapothiba |
| --- | --- | ---: | ---: | ---: | --- |
| `robot_pose` | `llm`, OpenCode | 2 | 1 | 127 | nincs |
| `hu_scene` | `llm`, OpenCode | 2 | 1 | 133 | nincs |

Mindkettő átment a meglévő geometriai feldolgozáson. Ez a rajzvonal
összefüggőségét jelzi, nem utcai útvonalat. A képi ellenőrzők ki voltak kapcsolva;
nincs független szemantikai pontszám. A bizonyíték helye:
`test-results/opencode-model-research/luna-shapes.json`.

`OPENCODE_TRANSPORT=api`, `OPENCODE_MODEL=gpt-6-luna`,
`OPENCODE_STRUCTURED_MODEL=gpt-6-luna`,
`OPENCODE_BASE_URL=https://opencode.ai/inference/openai/v1`.
A GPT-hívások Responses-t használnak egyszerű szöveghez is; GPT-6 esetén nincs
nem támogatott `temperature` paraméter. A szigorú séma, a geometriai validálás,
a javítási/újrapróbálási korlátok és az exporthoz szükséges utcai geometria
követelménye megmarad. A fizetős API nem indít helyi OpenCode szervert.

Az eredmények nem igazolják a teljes, élő utcai generálás alakfelismerését vagy
sebességét. Ehhez a projekt páros routing-provider benchmarkja szükséges.
