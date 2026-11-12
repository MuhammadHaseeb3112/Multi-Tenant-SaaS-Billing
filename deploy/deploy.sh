#!/usr/bin/env bash
# Update the server to the latest code on GitHub, with a health check and an
# automatic rollback.
#
#   cd ~/saas-billing && bash deploy/deploy.sh
#
# GitHub Actions runs this over SSH after CI passes on main
# (.github/workflows/deploy.yml). It can also be run by hand.
#
# 1. Tag the images that are running now as ":rollback".
# 2. Pull the new code, build, restart.
# 3. Wait for the backend health check and for the site through Caddy.
# 4. If either fails: go back to the previous commit and images.
#
# Migrations run on start (scripts/start-web.sh) and are not undone by a
# rollback, so keep them backward compatible (add columns; don't drop or
# rename them in the same release).
set -euo pipefail

# The braces make bash read the whole script before running it: "git reset"
# below may replace this file while it runs.
{
cd "$(dirname "$0")/.."
BRANCH="${DEPLOY_BRANCH:-main}"
ENV_FILE="deploy/.env.prod"
[ -f "$ENV_FILE" ] || { echo "Missing $ENV_FILE (see docs/DEPLOYMENT.md)"; exit 1; }

env_value() { grep -E "^$1=" "$ENV_FILE" | tail -n1 | cut -d= -f2- | tr -d '"' || true; }
DOMAIN="$(env_value DOMAIN)"

COMPOSE=(docker compose -f deploy/compose.prod.yml)
# Sharing the server with another Caddy (the external "edge" network exists):
# use the override that turns our own Caddy off.
if docker network inspect edge >/dev/null 2>&1; then
  COMPOSE+=(-f deploy/compose.shared-caddy.yml)
fi
COMPOSE+=(--env-file "$ENV_FILE")

log() { echo "[deploy $(date +%H:%M:%S)] $*"; }

# Images we build ourselves; databases and Caddy are pinned images.
own_images() { "${COMPOSE[@]}" config --images | grep -vE '^(postgres|redis|caddy)' | sort -u; }

healthy() {
  local web status
  for _ in $(seq 1 40); do
    web="$("${COMPOSE[@]}" ps -q web)"
    status="$(docker inspect -f '{{.State.Health.Status}}' "$web" 2>/dev/null || echo starting)"
    if [ "$status" = "healthy" ]; then
      # And through Caddy + the frontend's nginx, the way users reach it.
      if [ -z "$DOMAIN" ] || [ "$DOMAIN" = "localhost" ]; then
        curl -fsS http://localhost/api/health/ >/dev/null && return 0
      else
        curl -fsS --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN/api/health/" >/dev/null && return 0
      fi
    fi
    sleep 5
  done
  return 1
}

PREVIOUS="$(git rev-parse HEAD)"
log "Current version: ${PREVIOUS:0:7}"

for image in $(own_images); do
  if docker image inspect "$image" >/dev/null 2>&1; then
    docker tag "$image" "${image%%:*}:rollback"
  fi
done

git fetch --quiet origin "$BRANCH"
git reset --quiet --hard "origin/$BRANCH"   # deploy/.env.prod is git-ignored, so it stays
CURRENT="$(git rev-parse HEAD)"
log "New version: ${CURRENT:0:7}"

log "Building..."
"${COMPOSE[@]}" build
log "Starting..."
"${COMPOSE[@]}" up -d --remove-orphans

if healthy; then
  log "Healthy. Deployed ${CURRENT:0:7}."
  docker image prune -f >/dev/null || true
  exit 0
fi

log "Health check FAILED. Rolling back to ${PREVIOUS:0:7}..."
"${COMPOSE[@]}" logs --tail 80 web || true
git reset --quiet --hard "$PREVIOUS"
for image in $(own_images); do
  if docker image inspect "${image%%:*}:rollback" >/dev/null 2>&1; then
    docker tag "${image%%:*}:rollback" "$image"
  fi
done
"${COMPOSE[@]}" up -d --no-build --remove-orphans
if healthy; then
  log "Rolled back to ${PREVIOUS:0:7}; the site is up."
else
  log "Rollback is not healthy either. Check the logs of the web service."
fi
exit 1
}
