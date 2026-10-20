# Developing Paceasso with Ponytail

Ponytail's methods are installed in this repository, so the same instructions
travel with a checkout. Start with [AGENTS.md](https://github.com/ak91hu/CityShapeRunner/blob/master/AGENTS.md). The four upstream
skills are pinned to commit `09c434ab73ca43761c5d8b0c5d341926c2fba710`
(Ponytail 5.3.2); [the lock file](https://github.com/ak91hu/CityShapeRunner/blob/master/.agents/ponytail.lock.json) records their
SHA-256 hashes and [the MIT license](https://github.com/ak91hu/CityShapeRunner/blob/master/.agents/PONYTAIL-LICENSE) is retained.

## Working method

Read the request's actual input-to-output flow and every affected caller. Prefer
existing code, platform features and installed dependencies. Make one complete
change; keep validation, provider evidence, error handling and accessibility.
Run the relevant checks, review connected code, and report what was measured.
A change to a shared helper must update all its users.

On one workstation, run full pytest, browser suites, numerical benchmarks and
package builds sequentially. They can exceed Windows memory/commit limits when
combined even if each uses one worker. CI jobs on separate machines can remain
parallel. Keep failed reports and rerun only the checks affected by the fix or
resource failure.

Generated-route fixtures wait for result focus, the street map and lazy walkthrough header
before returning. Without these signals a late panel can move a pointer target
between mouse-down and mouse-up. The delayed-module regression in
`generation-experience.spec.js` keeps this readiness contract checked. Tests of
loading itself should use the lower-level mocks and submit helpers.

The local skills are available to skill-aware agents from the next turn:

| Skill | Purpose |
|---|---|
| `ponytail` | Apply the smallest complete solution; default `full` method. |
| `ponytail-review` | Review a named diff or files, trace callers and report concrete issues. |
| `ponytail-audit` | Map and audit the repository; state unread or untested areas. |
| `ponytail-debt` | Collect deliberate `shortcut:` comments and their revisit triggers. |

For example, ask: “Use ponytail-review on the current changes.” These are local
skills, not the namespaced commands of the full Ponytail plugin. `AGENTS.md`
provides the default project method even when a host has no skill commands.
The skills apply to development; they are not loaded into the application's
route-generation prompts. Original upstream wording is retained; project and
user instructions determine response language and authorized actions.

## Fast feedback without reducing the release checks

Install Python development dependencies and run `npm ci` in `frontend/` once.
Install Playwright engines once with `npx playwright install chromium firefox webkit`.
Run these frontend commands from `frontend/`:

| Change | First check | Additional behavior check |
|---|---|---|
| Frontend configuration or shared utilities | `npm run check` | Affected unit/spec if behavior changes. |
| Planner, results, waiting or general UI | `npm run check` | `npm run test:smoke` plus the affected feature spec. |
| Responsive layout, keyboard, dialogs | `npm run check` | `npm run test:smoke` and `npm run test:smoke:cross-browser`. |
| A single feature | `npm run check` | `npm run test:e2e -- editor-export-functional.spec.js` (replace with its actual spec). |
| Release | Complete CI quality gate | Full backend, Chromium, Firefox/WebKit, docs and container checks. |

`check` runs the existing frontend unit tests, then the production build; failure
stops the command. CI runs this same command before the frontend gate can pass.
The smoke suites cover accessibility, core usability and generation/waiting
experience on the configured desktop/mobile projects. They do not replace
editing, export, gallery or feature-specific tests. Use `-- --list` to inspect
the exact selected cases, or `-- --project=mobile-chromium` to narrow a local run.
Use the normal cross-browser command for all feature specs affected by a change.

From the repository root, using the project's Python environment:

```powershell
$env:GEOCODE_OFFLINE = "1"
python -m pytest -q tests/test_creative_search.py tests/test_generation_performance.py
python -m ruff check .
python -m mypy --ignore-missing-imports gps_art_wizzard
```

Choose the affected test files: API behavior in `test_api_contracts.py` and
`test_generation_integration.py`; streaming/cancellation in
`test_generation_stream.py` and `test_workflow_runtime.py`; shape geometry in
`test_shape_phase_alignment.py`, `test_algorithm_invariants.py` and
`test_route_safety.py`. Run the full backend suite before release.

For GPS search/scoring changes, retain the existing accuracy tools:

```powershell
python scripts/audit_generation_accuracy.py --baseline-ref <pre-change-commit> --output test-results/accuracy.json
python scripts/compare_generation_versions.py --help
```

The first command compares metrics on identical inputs and checks protected
quality/geometry files. It does not establish live route quality. Use the second
tool's paired live comparison only when claiming live quality or speed, with a
fixed input/snapshot, recorded provider provenance and an explicit baseline.
Keep invalid pairs and rate-limit failures visible. Never launch paid or live
generation merely to validate these development instructions.

## Small review, useful evidence

Use the PR template to record the problem, reuse decision and checks. Distinguish
executed checks from skipped checks; keep each result attached to the source it
tested. Do not infer a full-suite pass from several unrelated test subsets.
Benchmark durations are measurements of that command on that machine, not
promises about developer productivity or production latency.

To collect deliberate shortcuts manually:

```powershell
git grep --no-index --exclude-standard -nE '(#|//|/[*]) ?(shortcut|ponytail):'
```

Inspect hits: keyboard-shortcut notes or documentation examples are not debt.
Each actual deferral must state its limit and a trigger for revisiting it.

## Updating Ponytail

Review the upstream skill changes and license at a chosen commit. Install only
the four method directories, preserve the license and regenerate the hashes in
`.agents/ponytail.lock.json`. Do not silently track `main`. No runtime package,
lifecycle hook, task dashboard or telemetry service is needed for this setup.
The upstream benchmark numbers are not Paceasso measurements.
