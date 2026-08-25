#!/usr/bin/env bash
set -Eeuo pipefail

fail() {
  echo "::error title=Northflank deployment::$*"
  exit 1
}

for command_name in curl jq date; do
  command -v "$command_name" >/dev/null 2>&1 \
    || fail "Required command is unavailable: $command_name"
done

for variable_name in \
  NORTHFLANK_API_TOKEN \
  NORTHFLANK_PROJECT_ID \
  NORTHFLANK_SERVICE_ID \
  NORTHFLANK_PRODUCTION_URL \
  GITHUB_SHA; do
  [[ -n "${!variable_name:-}" ]] \
    || fail "Required GitHub Environment secret/variable is missing: $variable_name"
done

[[ "$GITHUB_SHA" =~ ^[0-9a-f]{40}$ ]] \
  || fail "GITHUB_SHA must be the full 40-character commit SHA supplied by GitHub."

for resource_id in "$NORTHFLANK_PROJECT_ID" "$NORTHFLANK_SERVICE_ID"; do
  [[ "$resource_id" =~ ^[A-Za-z0-9]+(-[A-Za-z0-9]+)*$ ]] \
    || fail "Northflank project and service IDs may contain only letters, numbers, and hyphens."
done

if [[ -n "${NORTHFLANK_TEAM_ID:-}" ]]; then
  [[ "$NORTHFLANK_TEAM_ID" =~ ^[A-Za-z0-9]+(-[A-Za-z0-9]+)*$ ]] \
    || fail "NORTHFLANK_TEAM_ID may contain only letters, numbers, and hyphens."
  api_root="https://api.northflank.com/v1/teams/${NORTHFLANK_TEAM_ID}/projects/${NORTHFLANK_PROJECT_ID}"
else
  api_root="https://api.northflank.com/v1/projects/${NORTHFLANK_PROJECT_ID}"
fi

[[ "$NORTHFLANK_PRODUCTION_URL" =~ ^https:// ]] \
  || fail "NORTHFLANK_PRODUCTION_URL must be an HTTPS URL."
production_url="${NORTHFLANK_PRODUCTION_URL%/}"
service_url="${api_root}/services/${NORTHFLANK_SERVICE_ID}"
authorization="Authorization: Bearer ${NORTHFLANK_API_TOKEN}"
response_file="$(mktemp)"
trap 'rm -f "$response_file"' EXIT

api_get() {
  local url="$1"
  curl --fail --silent --show-error \
    --retry 3 --retry-delay 2 --retry-all-errors \
    --header "$authorization" \
    "$url"
}

echo "Checking that direct Northflank CI cannot bypass the GitHub quality gate..."
api_get "$service_url" >"$response_file"
service_type="$(jq -r '.data.serviceType // empty' "$response_file")"
ci_disabled="$(jq -r '.data.disabledCI // false' "$response_file")"
# Northflank omits disabledCD when CD is enabled and only returns the field
# when the combined-service default is overridden. Treat an omitted value as
# enabled; an explicit true still blocks deployment.
cd_disabled="$(jq -r '.data.disabledCD // false' "$response_file")"
[[ "$service_type" == "combined" ]] \
  || fail "This workflow expects a Northflank combined service; received '${service_type:-unknown}'."
[[ "$ci_disabled" == "true" ]] \
  || fail "Disable CI on the Northflank combined service before enabling GitHub-controlled deployment."
[[ "$cd_disabled" == "false" ]] \
  || fail "Enable CD on the Northflank combined service so a successful exact-SHA build can roll out."

triggered_at_epoch="$(date -u +%s)"
echo "Requesting an exact-SHA Northflank build for ${GITHUB_SHA}..."
http_code="$(curl --silent --show-error \
  --output "$response_file" \
  --write-out '%{http_code}' \
  --header "$authorization" \
  --header 'Content-Type: application/json' \
  --request POST \
  --data "{\"sha\":\"${GITHUB_SHA}\"}" \
  "${service_url}/build")"

if [[ "$http_code" != "200" && "$http_code" != "201" ]]; then
  jq -c '{message: (.message // .error // "Northflank rejected the build request")}' \
    "$response_file" 2>/dev/null || true
  fail "Northflank build request returned HTTP ${http_code}."
fi

build_id="$(jq -r '.data.id // empty' "$response_file")"
accepted_sha="$(jq -r '.data.sha // empty' "$response_file")"
[[ -n "$build_id" ]] || fail "Northflank did not return a build ID."
[[ "$accepted_sha" == "$GITHUB_SHA" ]] \
  || fail "Northflank accepted SHA '${accepted_sha:-unknown}' instead of '${GITHUB_SHA}'."

build_deadline=$((SECONDS + ${NORTHFLANK_BUILD_TIMEOUT_SECONDS:-1800}))
last_build_status=""
build_succeeded="false"
while ((SECONDS < build_deadline)); do
  api_get "${service_url}/build/${build_id}" >"$response_file"
  build_status="$(jq -r '.data.status // "UNKNOWN"' "$response_file")"
  if [[ "$build_status" != "$last_build_status" ]]; then
    echo "Northflank build ${build_id}: ${build_status}"
    last_build_status="$build_status"
  fi

  if [[ "$(jq -r '.data.concluded // false' "$response_file")" == "true" ]]; then
    if [[ "$(jq -r '.data.success // false' "$response_file")" != "true" ]]; then
      build_message="$(jq -r '.data.message // "No build error message was returned."' "$response_file")"
      fail "Northflank build ${build_id} ended as ${build_status}: ${build_message}"
    fi
    build_succeeded="true"
    break
  fi
  sleep 15
done
[[ "$build_succeeded" == "true" ]] \
  || fail "Northflank build ${build_id} did not finish before the timeout."

echo "Build succeeded; waiting for Northflank CD to finish the new rollout..."
deployment_deadline=$((SECONDS + ${NORTHFLANK_DEPLOY_TIMEOUT_SECONDS:-900}))
last_deployment_status=""
deployment_completed="false"
while ((SECONDS < deployment_deadline)); do
  api_get "$service_url" >"$response_file"
  deployment_status="$(jq -r '.data.status.deployment.status // "UNKNOWN"' "$response_file")"
  transition_time="$(jq -r '.data.status.deployment.lastTransitionTime // empty' "$response_file")"

  if [[ "$deployment_status" != "$last_deployment_status" ]]; then
    echo "Northflank deployment: ${deployment_status}"
    last_deployment_status="$deployment_status"
  fi
  [[ "$deployment_status" != "FAILED" ]] \
    || fail "Northflank reported a failed production deployment."

  transition_epoch=0
  if [[ -n "$transition_time" ]]; then
    transition_epoch="$(date -u -d "$transition_time" +%s 2>/dev/null || echo 0)"
  fi
  if [[ "$deployment_status" == "COMPLETED" && "$transition_epoch" -ge "$triggered_at_epoch" ]]; then
    deployment_completed="true"
    break
  fi
  sleep 10
done
[[ "$deployment_completed" == "true" ]] \
  || fail "The new Northflank deployment did not complete before the timeout."

echo "Verifying the public production health contract..."
curl --fail --silent --show-error \
  --retry 15 --retry-delay 4 --retry-all-errors \
  "${production_url}/health" >"$response_file"
jq --exit-status '.status == "ok"' "$response_file" >/dev/null \
  || fail "The deployed service did not return the expected health payload."

echo "Northflank deployed and verified build ${build_id} for ${GITHUB_SHA}."
if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  {
    echo "### Northflank production deployment"
    echo
    echo "- Commit: \`${GITHUB_SHA}\`"
    echo "- Build: \`${build_id}\`"
    echo "- Health: \`${production_url}/health\`"
  } >>"$GITHUB_STEP_SUMMARY"
fi
