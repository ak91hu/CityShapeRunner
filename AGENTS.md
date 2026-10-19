# Paceasso development

## Documentation layout

Keep maintained documentation in the appropriate `docs/` section listed in
`docs/index.md`; put dated reviews in `docs/reports/`. Only root `README.md`,
root `AGENTS.md` and tool-discovered skill/PR-template Markdown stay outside
`docs/`. Generated evidence belongs in ignored `test-results/` directories.
After moving documents, update their links, MkDocs navigation, code readers,
package metadata and Docker copy paths. Run `python scripts/check_documentation.py`
and `python -m mkdocs build --strict`.

Use the Ponytail method by default: understand the real flow, then make the
smallest change that completely solves the task. The vendored methods live in
`.agents/skills/`; source revision and license are recorded in `.agents/`.

## Before editing

- Read the affected code, callers, tests, fixtures and configuration. Search all
  callers before changing shared behavior; fix the cause in the shared code.
- Reuse an existing project helper or component first, then the standard library
  or platform, then an installed dependency. Add a dependency only when needed.
- Preserve existing conventions. Avoid speculative options, wrappers and broad
  rewrites. Finish all callers and fixtures that the requested change affects.
- Preserve uncommitted work. Read `docs/architecture/agents.md` before changing runtime
  agents, prompts, application skills or the orchestrator. Development skills
  under `.agents/` are separate from runtime `docs/skills/skill-*.md` prompts.

## Application map and invariants

- `gps_art_wizzard/api/routes.py` → `orchestrator.py` → agents/tools → validation
  and export. The frontend uses `frontend/src/api.js` and streamed progress.
- Public routes and exports require actual connected routing-provider geometry.
  Never substitute an ideal outline or snapped points for a street route.
- Do not relax quality thresholds, distance/closure/connectivity checks, metric
  resolution, repair budgets or API validation to claim a speed improvement.
- Preserve cancellation, error diagnosis, bounded retries, secrets handling,
  accessibility, keyboard focus and mobile reflow.
- Progress describes real server work. Synthetic fixtures and isolated timings
  cannot establish live generation speed or GPS-art accuracy.

## Feedback loop

1. State the intended behavior and affected paths briefly; implement it.
2. Run the smallest relevant existing checks from `docs/development/workflow.md`. New risky
   logic or a bug fix needs a meaningful regression test. Simple configuration
   and wording changes need direct validation, not tests of their own wording.
3. For frontend changes start with `npm run check` in `frontend/`; use
   `npm run test:smoke` for the main flows and run affected feature specs too.
   Responsive/focus changes also need the corresponding cross-browser checks.
4. GPS search/scoring changes need the relevant backend tests and same-input
   accuracy audit. Claims about live quality or latency need the existing
   paired provider benchmark, including failures and provenance.
5. Before release, keep the complete CI quality gate. A smoke suite is local
   feedback, not evidence that unrun features pass. After a passing check,
   repeat it only if another change or new evidence requires it.

## Review and reporting

Review correctness, safety, realistic load, missing tests, speed and unnecessary
code, in that order. Read connected code, not just the diff. Report only findings
with a concrete failure case, smallest fix and consequence of leaving it.
Record deliberate limits as `shortcut: <limit>, <trigger to revisit>` comments;
the `ponytail-debt` skill collects them. Do not invent debt markers for routine code.

Reply in the user's language. Describe the change and measured checks concisely;
end with any material unverified behavior or remaining risk. Never transfer
Ponytail's upstream benchmark percentages to this application as measured gains.
