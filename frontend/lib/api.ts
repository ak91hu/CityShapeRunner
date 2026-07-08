import type {
  Activity,
  ArtworkDetail,
  ArtworkSummary,
  CandidateSummary,
  CityCompatibility,
  CityDetail,
  CitySuggestion,
  Difficulty,
  GenerationJobCreated,
  GenerationJobStatus,
  HealthResponse,
  RouteDetail,
  ShapeCompatibility,
  ShareView,
} from "./types";

const BASE = "";

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + url, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = (body?.error?.message) || res.statusText;
    throw new Error(err);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => json<HealthResponse>(`/api/health`),
  ready: () => json<HealthResponse>(`/api/ready`),

  searchCities: (q: string, country?: string) =>
    json<{ items: CitySuggestion[] }>(
      `/api/cities/search?q=${encodeURIComponent(q)}${country ? `&country=${country}` : ""}`,
    ).then((r) => r.items),

  listAllCities: () =>
    json<{ items: CityDetail[] }>(`/api/cities`).then((r) => r.items),

  getCity: (cityId: string) => json<CityDetail>(`/api/cities/${cityId}`),

  listArtworks: (params?: { distanceKm?: number; activity?: Activity; cityId?: string }) => {
    const qs = new URLSearchParams();
    if (params?.distanceKm) qs.set("distanceKm", String(params.distanceKm));
    if (params?.activity) qs.set("activity", params.activity);
    if (params?.cityId) qs.set("cityId", params.cityId);
    const q = qs.toString();
    return json<{ items: ArtworkSummary[] }>(`/api/artworks${q ? `?${q}` : ""}`).then((r) => r.items);
  },

  getArtwork: (artworkId: string) => json<ArtworkDetail>(`/api/artworks/${artworkId}`),

  getCompatibleCities: (artworkId: string, activity?: string, difficulty?: string) =>
    json<{ artworkId: string; items: CityCompatibility[] }>(
      `/api/artworks/${artworkId}/cities?activity=${activity || "running"}&difficulty=${difficulty || "medium"}`,
    ),

  getCityArtworks: (cityId: string, activity?: string, difficulty?: string) =>
    json<{ cityId: string; items: ShapeCompatibility[] }>(
      `/api/cities/${cityId}/artworks?activity=${activity || "running"}&difficulty=${difficulty || "medium"}`,
    ),

  createJob: (req: {
    cityId: string;
    activity: Activity;
    targetDistanceKm: number;
    difficulty: Difficulty;
    maxSuggestions: number;
    artworkIds?: string[];
  }) => json<GenerationJobCreated>(`/api/generation/jobs`, {
    method: "POST",
    body: JSON.stringify(req),
  }),

  getJob: (jobId: string) => json<GenerationJobStatus>(`/api/generation/jobs/${jobId}`),

  cancelJob: (jobId: string) =>
    json<GenerationJobStatus>(`/api/generation/jobs/${jobId}/cancel`, { method: "POST" }),

  getCandidate: (candidateId: string) => json<CandidateSummary>(`/api/candidates/${candidateId}`),

  candidateGeoJson: (candidateId: string) =>
    fetch(`/api/candidates/${candidateId}/geojson`).then(
      (r) => r.json() as Promise<GeoJSON.FeatureCollection>,
    ),

  createRoute: (candidateId: string) =>
    json<RouteDetail>(`/api/routes`, { method: "POST", body: JSON.stringify({ candidateId }) }),

  getRoute: (routeId: string) => json<RouteDetail>(`/api/routes/${routeId}`),

  createShare: (routeId: string) =>
    json<{ shareId: string; shareUrl: string }>(`/api/routes/${routeId}/share`, {
      method: "POST",
    }),

  getShare: (shareId: string) => json<ShareView>(`/api/share/${shareId}`),

  gpxUrl: (routeId: string, mode: "continuous" | "connect_the_dots") =>
    `/api/routes/${routeId}/export/gpx?mode=${mode}`,
};
