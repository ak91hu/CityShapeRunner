export type Activity = "running" | "cycling" | "walking";
export type Difficulty = "easy" | "medium" | "hard";
export type JobStatus = "queued" | "processing" | "completed" | "failed" | "cancelled";
export type ExportMode = "continuous" | "connect_the_dots";

export interface GeoPoint { lat: number; lon: number; }

export interface CitySuggestion {
  id: string;
  name: string;
  country: string;
  countryCode: string;
  osmId?: number;
  bbox: [number, number, number, number];
  centroid: GeoPoint;
}

export interface CityDetail extends CitySuggestion {
  boundaryGeojson?: GeoJSON.FeatureCollection | null;
  roadDensity?: number | null;
  hasRiver?: boolean | null;
  bridgeCount?: number | null;
  signatureArtworkIds: string[];
  cityAffinityTags?: string[];
}

export interface ArtworkSummary {
  id: string;
  name: string;
  category: string;
  complexity: string;
  recommendedMinKm: number;
  recommendedMaxKm: number;
  aspectRatio: number;
  isCitySignature: boolean;
  previewSvgUrl: string;
  tags: string[];
  cityAffinityTags: string[];
}

export interface ArtworkDetail extends ArtworkSummary {
  closedPath: boolean;
  defaultSampleCount: number;
  normalizedLength: number;
  symmetric: boolean;
}

export interface ScoreBreakdown {
  fitScore: number;
  shapeSimilarityScore: number;
  distanceAccuracyScore: number;
  roadQualityScore: number;
  continuityScore: number;
  elevationScore: number;
}

export interface CandidateSummary {
  candidateId: string;
  artworkId: string;
  artworkName: string;
  rank: number;
  distanceKm: number;
  elevationGainM?: number | null;
  scores: ScoreBreakdown;
  fitScore: number;
  shapeSimilarityScore: number;
  roadQualityScore: number;
  warnings: string[];
  previewGeoJsonUrl: string;
  targetGeoJsonUrl?: string | null;
  debug?: Record<string, unknown>;
}

export interface GenerationJobCreated { jobId: string; status: JobStatus; }

export interface GenerationJobStatus {
  jobId: string;
  status: JobStatus;
  progressStage?: string | null;
  progressPercent: number;
  errorCode?: string | null;
  errorMessage?: string | null;
  suggestions: CandidateSummary[];
}

export interface RouteDetail {
  routeId: string;
  cityId: string;
  artworkId: string;
  artworkName: string;
  activity: Activity;
  distanceKm: number;
  elevationGainM?: number | null;
  scores: ScoreBreakdown;
  warnings: string[];
  gpxUrl: string;
  gpxConnectTheDotsUrl?: string | null;
  shareUrl?: string | null;
  visibility: string;
}

export interface ShareView {
  shareId: string;
  routeId: string;
  cityName: string;
  artworkName: string;
  activity: Activity;
  distanceKm: number;
  geojson: GeoJSON.FeatureCollection;
}

export interface HealthResponse {
  status: string;
  version: string;
  db: boolean;
}

export interface SnapEditResponse {
  lonlat: number[][];
  snapped: boolean;
  warnings: string[];
  originalLonlat: number[][];
  segmentsFailed: number;
}

export interface CityCompatibility {
  cityId: string;
  cityName: string;
  fitScore: number;
  minKm: number;
  maxKm: number;
  recommendedKm: number;
  isSignature: boolean;
}

export interface ShapeCompatibility {
  artworkId: string;
  artworkName: string;
  category: string;
  complexity: string;
  previewSvgUrl: string;
  fitScore: number;
  minKm: number;
  maxKm: number;
  recommendedKm: number;
  isSignature: boolean;
}

export const STAGE_MESSAGES: Record<string, string> = {
  loading_city: "Loading city geometry",
  loading_road_graph: "Loading streets, paths & cycleways",
  selecting_artworks: "Choosing shapes that fit",
  generating_placements: "Finding good placements",
  fitting_candidates: "Testing rotations, sizes & placements",
  repairing_routes: "Connecting route along real roads",
  scoring: "Ranking the best-looking routes",
  storing_results: "Preparing previews",
  completed: "Done",
};

export const STAGE_ORDER = [
  "loading_city", "loading_road_graph", "selecting_artworks", "generating_placements",
  "fitting_candidates", "repairing_routes", "scoring", "storing_results", "completed",
];

export const ACTIVITY_ICONS: Record<Activity, string> = {
  running: "M13 4l3 3-3 3M11 20l-3-3 3-3M9 8l-2 2 2 2M15 16l2-2-2-2",
  cycling: "M5 18a3 3 0 100-6 3 3 0 000 6zM19 18a3 3 0 100-6 3 3 0 000 6z",
  walking: "M13 5l1.5 4.5L13 14l-2 4M9 20l2-4 2-2 2 4",
};

export const CATEGORIES: string[] = ["basic", "animals", "sports", "nature", "city", "funny", "symbols"];
export const COMPLEXITIES: string[] = ["easy", "medium", "hard"];
