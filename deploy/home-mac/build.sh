#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
: "${BASE_IMAGE:=ghcr.io/maziggy/bambuddy@sha256:807f67511fa8c2b644b09de50a5d41794372214d00bd04fda59f576d9958d280}"
: "${HOME_IMAGE:=bambuddy-home:20261019}"
: "${HOME_DOCKER_CONFIG:=$HOME/.ops/3d-printing/docker-public}"
endpoint=$(docker context inspect --format '{{.Endpoints.docker.Host}}')
COPYFILE_DISABLE=1 tar --no-xattrs -cf - backend/app/api/routes/home_ledger.py backend/app/services/home_ledger_store.py static deploy/home-mac/Dockerfile |
 DOCKER_HOST="$endpoint" docker --config "$HOME_DOCKER_CONFIG" build -f deploy/home-mac/Dockerfile --build-arg "BASE_IMAGE=$BASE_IMAGE" -t "$HOME_IMAGE" -
