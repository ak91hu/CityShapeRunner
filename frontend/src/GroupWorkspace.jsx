import { lazy, Suspense, useEffect, useId, useRef, useState } from "react";
import { createMuralPlan } from "./api.js";
import { parseGroupProject } from "./groupProject.js";

const RouteMap = lazy(() => import("./RouteMap.jsx"));

export default function GroupWorkspace({ activeRoute, name = "Community drawing", sport = "run",
  routePreferences = {}, eligible = true, saveFile, renderCompletion, onOpenCampaignBuilder }) {
  const headingId = useId();
  const [eventName, setEventName] = useState(name.slice(0, 100));
  const nextId = useRef(3);
  const [members, setMembers] = useState([
    { id: 1, name: "Artist 1", max_distance_km: 10 },
    { id: 2, name: "Artist 2", max_distance_km: 10 },
  ]);
  const [returnToStart, setReturnToStart] = useState(false);
  const [imported, setImported] = useState(null);
  const [plan, setPlan] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [overlay, setOverlay] = useState(null);
  const [restoredReviewed, setRestoredReviewed] = useState(false);
  const requestRef = useRef(null);
  const resultRef = useRef(null);
  useEffect(() => () => requestRef.current?.abort(), []);
  useEffect(() => {
    requestRef.current?.abort();
    setBusy(false); setPlan(null); setOverlay(null); setImported(null);
  }, [activeRoute?.points_preview, activeRoute?.id, eligible]);
  const source = imported ? { points_preview: imported.points } : activeRoute;
  const eventSport = imported?.sport ?? (sport === "bike" ? "bike" : "run");
  const invalidate = () => { setPlan(null); setOverlay(null); setError(""); setRestoredReviewed(false); };
  const updateMember = (id, field, value) => {
    invalidate();
    setMembers(current => current.map(member => member.id === id ? { ...member, [field]: value } : member));
  };
  const payload = () => ({
    name: eventName.trim(), points: source.points_preview,
    members: members.map(({ name, max_distance_km }) => ({ name: name.trim(), max_distance_km: Number(max_distance_km) })),
    sport: eventSport, return_to_start: returnToStart,
    route_preferences: imported?.route_preferences ?? routePreferences,
  });
  const create = async event => {
    event.preventDefault();
    const request = payload();
    if (!request.name || request.members.some(member => !member.name)) {
      setError("Enter an event name and a name for every participant.");
      return;
    }
    const names = request.members.map(member => member.name.toLocaleLowerCase());
    if (new Set(names).size !== names.length) {
      setError("Participant names must be distinct.");
      return;
    }
    const controller = new AbortController();
    requestRef.current?.abort();
    requestRef.current = controller;
    setBusy(true); invalidate();
    try {
      const response = await createMuralPlan(request, { signal: controller.signal });
      if (controller.signal.aborted) return;
      setPlan({ ...response, sourcePoints: activeRoute?.points_preview, sourceId: activeRoute?.id,
        request });
    } catch (requestError) {
      if (!controller.signal.aborted) setError(requestError.message || "We couldn’t prepare this group event.");
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  };
  const load = async event => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    try {
      if (file.size > 1_000_000) throw new Error("The event file is too large (maximum 1 MB).");
      const saved = parseGroupProject(await file.text());
      requestRef.current?.abort(); setBusy(false); invalidate();
      setImported(saved); setEventName(saved.name); setReturnToStart(saved.return_to_start);
      setMembers(saved.members.map(member => ({ ...member, id: nextId.current++ })));
    } catch (loadError) { setError(loadError.message); }
  };
  const showSection = section => setOverlay({ type: "assignment", segments: [
    { id: section.id, label: `${section.label}: drawing section`, points_preview: section.points_preview },
    ...(section.travel_segments_preview ?? []).map((points, index) => ({
      id: `${section.id}-travel-${index}`, label: `${section.label}: meeting-point travel`,
      kind: "dark", points_preview: points,
    })),
  ] });
  const usablePlan = plan && (imported || (eligible && plan.sourcePoints === activeRoute?.points_preview && plan.sourceId === activeRoute?.id));
  const checkedRoute = usablePlan ? { ...source, points_preview: plan.points_preview, snapped: true } : null;
  useEffect(() => {
    if (!usablePlan) return undefined;
    const frame = window.requestAnimationFrame(() => resultRef.current?.focus());
    return () => window.cancelAnimationFrame(frame);
  }, [plan, usablePlan]);
  return (
    <section className="group-workspace" aria-labelledby={headingId}>
      <h2 id={headingId}>Create together</h2>
      <p>One drawing, different distances. Assign sections, record your outings, then complete the picture together.</p>
      <div className="group-event-actions">
        <label className="button button--secondary group-import">
          Open saved event
          <input type="file" accept=".json,application/json" onChange={load} disabled={busy} />
        </label>
        {onOpenCampaignBuilder && <button type="button" className="button button--secondary" onClick={onOpenCampaignBuilder}>Organise a campaign</button>}
      </div>
      {imported && <p role="status">Loaded {imported.name}. Check the saved route against current streets before using its assignments.</p>}
      {!source && <p>Start by creating a street drawing below, or open an event saved on this device.</p>}
      {source && <form className="mural-card group-plan-form" onSubmit={create}>
        <h3>Assign the drawing</h3>
        {!eligible && !imported && <p>Apply or discard pending point edits, then review and approve this street route in the download panel before preparing group GPS files.</p>}
        <fieldset disabled={busy || (!eligible && !imported)}>
          <legend className="sr-only">Event and participants</legend>
          <label>Event name<input value={eventName} required maxLength={100} onChange={event => { invalidate(); setEventName(event.target.value); }} /></label>
          <p>Set a maximum for each person or team. Shorter limits receive shorter drawing sections. {eventSport === "bike" ? "These are cycling routes." : "Participants can run or walk the foot routes."}</p>
          <ol className="group-members">
            {members.map((member, index) => <li key={member.id}>
              <label>Participant {index + 1}<input value={member.name} required maxLength={80} onChange={event => updateMember(member.id, "name", event.target.value)} /></label>
              <label>Maximum km<span className="sr-only"> for participant {index + 1}</span><input type="number" min="0.05" max="500" step="0.05" required value={member.max_distance_km} onChange={event => updateMember(member.id, "max_distance_km", event.target.value)} /></label>
              <button type="button" className="button button--quiet" disabled={members.length <= 2} aria-label={`Remove participant ${index + 1}`} onClick={() => { invalidate(); setMembers(current => current.filter(item => item.id !== member.id)); }}>Remove</button>
            </li>)}
          </ol>
          <button type="button" className="button button--secondary" disabled={members.length >= 24} onClick={() => {
            invalidate(); const id = nextId.current++;
            setMembers(current => [...current, { id, name: `Artist ${id}`, max_distance_km: 10 }]);
          }}>Add participant</button>
          <label className="group-meeting"><input type="checkbox" checked={returnToStart} onChange={event => { invalidate(); setReturnToStart(event.target.checked); }} />Meet and return at the drawing’s start</label>
          <p>{returnToStart ? "Street-routed travel to and from each section counts towards the maximum. Some allocations may not fit. Record the whole outing; travel can add lines outside the drawing." : "Each person meets at their section’s start. Travel there and home is not included; use the shared meeting point to include it in the maximum."}</p>
          <button type="submit" className="button button--primary">Create mural plan</button>
        </fieldset>
        {busy && <p role="status">Checking the street route and each participant’s distance…</p>}
        {busy && <button type="button" className="button button--quiet" onClick={() => {
          requestRef.current?.abort(); setBusy(false);
        }}>Cancel group check</button>}
      </form>}
      {error && <p className="editor-error" role="alert">{error}</p>}
      {usablePlan && <div className="group-event-result" tabIndex={-1} ref={resultRef}>
        <h3>{plan.request.name}: assignments ready</h3>
        <p>{plan.travel_note}</p>
        {plan.meeting_point && <p>Shared meeting point: {plan.meeting_point.map(value => value.toFixed(5)).join(", ")}</p>}
        <p>Review local access and crossings before the event. Send each person their GPX and start/finish details.</p>
        {imported && <label className="group-meeting"><input type="checkbox" checked={restoredReviewed} onChange={event => setRestoredReviewed(event.target.checked)} />I reviewed the restored street drawing, section endpoints and local access.</label>}
        <button type="button" className="button button--secondary" onClick={() => saveFile("paceasso-event.json", JSON.stringify({ format: "paceasso-group-v1", ...plan.request }, null, 2), "application/json")}>Save event plan</button>
        <p>The saved file includes names and route coordinates. Keep it for the event’s return visit; nothing is saved to an account.</p>
        <ul className="mural-sections group-assignments">
          {plan.sections.map(section => <li key={section.id}>
            <strong>{section.label}, {section.distance_km.toFixed(2)} km total</strong>
            <span>{section.art_distance_km.toFixed(2)} km drawing · {section.travel_distance_km.toFixed(2)} km travel · maximum {section.max_distance_km} km</span>
            <span>Section start: {section.start.map(value => value.toFixed(5)).join(", ")} · finish: {section.finish.map(value => value.toFixed(5)).join(", ")}</span>
            <div className="group-event-actions">
              <button type="button" className="button button--secondary" onClick={() => showSection(section)}>Show {section.label} on map</button>
              <button type="button" className="button button--secondary" disabled={imported && !restoredReviewed} onClick={() => saveFile(`${section.id}.gpx`, section.gpx, "application/gpx+xml")}>GPX for {section.label}</button>
            </div>
          </li>)}
        </ul>
        <Suspense fallback={<p role="status">Loading event map…</p>}>
          <RouteMap points={plan.points_preview} roadRouted shapeName={plan.request.name} analysisSegments={overlay?.segments ?? []} />
        </Suspense>
        {(!imported || restoredReviewed) && renderCompletion?.({ activeRoute: checkedRoute, shapeName: plan.request.name, city: "", sport: eventSport,
          overlayType: overlay?.type, onOverlayChange: setOverlay, group: true })}
      </div>}
    </section>
  );
}
