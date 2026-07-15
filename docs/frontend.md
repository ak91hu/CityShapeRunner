# Frontend

The frontend is a Next.js 15 App Router application with TypeScript.

## Pages

| Path | Description |
|---|---|
| `/` | Landing page - search, feature overview, and call-to-action |
| `/studio` | Generation studio - 3-step wizard to create GPS art |
| `/gallery` | Artwork library - browse 500 shapes by category and difficulty |
| `/cities` | City explorer - browse 2000 global cities with road network stats |
| `/cities/[id]` | City detail - featured shapes and compatibility |
| `/artworks/[id]` | Artwork detail - metadata, city affinities, how it works |
| `/routes/[id]` | Route detail - scores, GPX downloads, share link |
| `/share/[code]` | Shared route view |

## Key components

| Component | Location | Purpose |
|---|---|---|
| `CitySearch` | `components/CitySearch.tsx` | Search-as-you-type city selector |
| `ArtworkCard` | `components/ArtworkCard.tsx` | Shape preview card with metadata |
| `ShapeOpportunities` | `components/ShapeOpportunities.tsx` | Compatible shapes for a selected city |
| `StudioWizard` | `components/StudioWizard.tsx` | Step-by-step generation flow |
| `CompatCityList` | `components/CompatCityList.tsx` | Cities compatible with a selected shape |
| `MapView` | `components/MapView.tsx` | Leaflet-based route + target overlay |
| `ResultCard` | `components/ResultCard.tsx` | Candidate result with scores |
| `NavBar` | `components/NavBar.tsx` | Top navigation + language toggle |
| `ProgressPanel` | `components/ProgressPanel.tsx` | Real-time stage progress during generation |

## State management

- **API data** - fetched client-side via `lib/api.ts` (wrapper around `fetch`)
- **Generation flow** - state lifted to `StudioWizard` (shape, city, activity, distance)
- **Job polling** - `useEffect` with exponential backoff polls `GET /api/generation/jobs/{id}`
- **I18n** - React context provider in `lib/i18n.tsx`, supports HU/EN toggle

## API client

Everything goes through `lib/api.ts`:

```typescript
import { api } from "@/lib/api";

// Typed response
const cities = await api.getCities();
const artworks = await api.getCityArtworks("budapest", { activity: "running" });
const job = await api.generate({ cityId: "budapest", artworkId: "heart", activity: "running", distanceKm: 8 });
```

## Styling

- Tailwind CSS v4
- Components follow a shared design language (card, button, input styles)
- Responsive - works on mobile and desktop
- Hungarian default, English toggle in navbar

## Internationalization

Keys are defined in `lib/i18n.tsx` under the `hu` and `en` dicts. Used via:

```typescript
const { t } = useI18n();
return <h1>{t("landing.title1")}</h1>;
```

## Build & dev

```bash
cd frontend
npm install
npm run dev      # Dev server on :3000
npm run build    # Production build
npm start        # Production server
```
