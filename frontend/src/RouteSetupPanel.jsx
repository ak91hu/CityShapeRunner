import {
  START_DIRECTIONS,
  countRouteSetupSelections,
  routeSetupSummary,
} from "./routeSetup.js";

const START_CHOICES = [
  {
    value: "any",
    title: "Flexible start",
    description: "Let the planner choose the strongest nearby street grid.",
  },
  {
    value: "address",
    title: "Address or place",
    description: "Anchor the first and last point near a place you know.",
  },
  {
    value: "location",
    title: "Current location",
    description: "Use this device’s position for this request only.",
  },
];

const ROUTE_PREFERENCE_OPTIONS = [
  {
    key: "avoid_steps",
    title: "Avoid steps",
    description: "Keep the route on step-free ways where map data allows.",
  },
  {
    key: "avoid_ferries",
    title: "Avoid ferries",
    description: "Do not include water crossings that require a ferry.",
  },
  {
    key: "avoid_fords",
    title: "Avoid fords",
    description: "Avoid mapped crossings that pass directly through water.",
  },
  {
    key: "prefer_quiet",
    title: "Prefer quiet streets",
    description: "Running and walking routes only.",
  },
  {
    key: "prefer_green",
    title: "Prefer green ways",
    description: "Running and walking routes only.",
  },
];

function StepHeading({ number, title, description }) {
  return (
    <div className="route-setup-step-heading">
      <span aria-hidden="true">{number}</span>
      <div>
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
    </div>
  );
}

export default function RouteSetupPanel({
  loading,
  locationBusy,
  locationError,
  routePreferences,
  startAddress,
  startDirection,
  startMode,
  startPoint,
  onCurrentLocation,
  onPreferenceChange,
  onReset,
  onStartAddressChange,
  onStartDirectionChange,
  onStartModeChange,
}) {
  const setup = {
    startMode,
    startAddress,
    startPoint,
    startDirection,
    routePreferences,
  };
  const selectedCount = countRouteSetupSelections(setup);

  return (
    <details className="planning-options-panel route-setup-panel">
      <summary>
        <span className="route-setup-summary-copy">
          <span className="route-setup-summary-title">
            <strong>Route setup</strong>
            {selectedCount > 0 && <em>{selectedCount} active</em>}
          </span>
          <small>{routeSetupSummary(setup)}</small>
        </span>
        <b aria-hidden="true">+</b>
      </summary>

      <div className="planning-options-body route-setup-body">
        <div className="route-setup-intro">
          <div>
            <span className="route-setup-kicker">Optional controls</span>
            <h2>Fine-tune how the route starts and which streets it uses</h2>
            <p>These constraints are sent to street routing and change the generated GPX.</p>
          </div>
          {selectedCount > 0 && (
            <button
              type="button"
              className="button button--quiet route-setup-reset"
              onClick={onReset}
              disabled={loading || locationBusy}
            >
              Reset setup
            </button>
          )}
        </div>

        <section className="route-setup-step" aria-labelledby="route-start-title">
          <StepHeading
            number="1"
            title="Choose the start"
            description="Start anywhere, enter a place, or use this device’s location."
          />
          <fieldset className="route-start-fieldset">
            <legend className="sr-only" id="route-start-title">Start point</legend>
            <div className="route-start-options">
              {START_CHOICES.map((choice) => (
                <label key={choice.value} className="route-choice-card">
                  <input
                    type="radio"
                    name="route-start-mode"
                    value={choice.value}
                    checked={startMode === choice.value}
                    onChange={() => onStartModeChange(choice.value)}
                    disabled={loading || locationBusy}
                  />
                  <span>
                    <strong>{choice.title}</strong>
                    <small>{choice.description}</small>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>

          {startMode === "address" && (
            <div className="field route-start-detail">
              <label htmlFor="start-address">Start address or place</label>
              <input
                id="start-address"
                type="text"
                value={startAddress}
                maxLength={180}
                placeholder="Heroes’ Square, Budapest"
                autoComplete="street-address"
                aria-describedby="start-address-help"
                onChange={(event) => onStartAddressChange(event.target.value)}
                disabled={loading || locationBusy}
              />
              <small id="start-address-help" className="field-hint">
                Include the city or postcode so the start can be resolved unambiguously.
              </small>
            </div>
          )}

          {startMode === "location" && (
            <div className="route-start-detail route-location-detail">
              <div>
                <strong>{startPoint ? "Location ready" : "Location not selected yet"}</strong>
                <small>
                  {startPoint
                    ? `${startPoint.latitude.toFixed(5)}, ${startPoint.longitude.toFixed(5)}`
                    : "Your browser will ask for permission when you continue."}
                </small>
              </div>
              <button
                type="button"
                className="button button--secondary"
                onClick={onCurrentLocation}
                disabled={loading || locationBusy}
              >
                {locationBusy ? "Finding location…" : startPoint ? "Refresh location" : "Use my location"}
              </button>
            </div>
          )}

          {startMode === "location" && startPoint && (
            <p className="planning-status" role="status">
              Current location selected for this request only.
            </p>
          )}
          {locationError && startMode === "location" && (
            <p className="field-error" role="alert">
              <span aria-hidden="true">!</span>
              {locationError}
            </p>
          )}
        </section>

        <section className="route-setup-step" aria-labelledby="route-direction-title">
          <StepHeading
            number="2"
            title="Set the first heading"
            description="The street router will keep the first segment within about 45° of this direction."
          />
          <fieldset className="direction-fieldset">
            <legend className="sr-only" id="route-direction-title">First heading</legend>
            <div className="direction-compass">
              {START_DIRECTIONS.map((direction) => (
                <label key={direction.label} title={direction.label}>
                  <input
                    type="radio"
                    name="preferred-start-direction"
                    value={direction.value}
                    aria-label={direction.label}
                    checked={startDirection === direction.value}
                    onChange={() => onStartDirectionChange(direction.value)}
                    disabled={loading}
                  />
                  <span aria-hidden="true">{direction.glyph}</span>
                  <small>{direction.shortLabel}</small>
                  <span className="sr-only">{direction.label}</span>
                </label>
              ))}
            </div>
          </fieldset>
        </section>

        <section className="route-setup-step" aria-labelledby="route-streets-title">
          <StepHeading
            number="3"
            title="Choose street priorities"
            description="Hard avoids are applied whenever supported; quiet and green weighting is for running."
          />
          <fieldset className="route-preferences-fieldset">
            <legend className="sr-only" id="route-streets-title">Street priorities</legend>
            <div className="route-preference-grid">
              {ROUTE_PREFERENCE_OPTIONS.map((preference) => (
                <label key={preference.key} className="route-preference-card">
                  <input
                    type="checkbox"
                    checked={routePreferences[preference.key]}
                    onChange={(event) => onPreferenceChange(preference.key, event.target.checked)}
                    disabled={loading}
                  />
                  <span>
                    <strong>{preference.title}</strong>
                    <small>{preference.description}</small>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
        </section>

        <p className="route-setup-footnote">
          Start and heading are not combined with manual map placement; street priorities still apply.
        </p>
      </div>
    </details>
  );
}
