#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if [[ "${1:-}" == "admin-password" ]]; then
  if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 is required to configure the admin password." >&2
    exit 1
  fi
  if [[ ! -f .env ]]; then
    cp .env.example .env
  fi
  python3 backend/admin_setup.py .env
  exit $?
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required but was not found." >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running. Start Docker and run ./run.sh again." >&2
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose is required but was not found." >&2
  exit 1
fi

case "${1:-up}" in
  down|stop)
    docker compose down
    exit 0
    ;;
  logs)
    docker compose logs -f --tail=200
    exit 0
    ;;
  status)
    docker compose ps
    exit 0
    ;;
  up|start)
    ;;
  *)
    echo "Usage: ./run.sh [up|down|logs|status|admin-password]" >&2
    exit 2
    ;;
esac

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env. Add a read-only GITHUB_TOKEN, then run ./run.sh again." >&2
  exit 2
fi
if ! grep -Eq '^GITHUB_TOKEN=.+$' .env || grep -Eq '^GITHUB_TOKEN=(github_pat_replace_me|replace_me)$' .env; then
  echo "Set a read-only GITHUB_TOKEN in .env, then run ./run.sh again." >&2
  exit 2
fi
if ! grep -Eq '^ADMIN_PASSWORD_HASH=pbkdf2_sha256:' .env \
  || ! grep -Eq '^ADMIN_SESSION_SECRET=.{32,}$' .env; then
  if [[ -t 0 ]] && command -v python3 >/dev/null 2>&1; then
    echo "First run: configure the local administration account."
    python3 backend/admin_setup.py .env
  else
    echo "Admin credentials are not configured. Run ./run.sh admin-password first." >&2
    exit 2
  fi
fi

port_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -H -ltn "sport = :$port" 2>/dev/null | grep -q .
  elif command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
  else
    (exec 3<>"/dev/tcp/127.0.0.1/$port") >/dev/null 2>&1
  fi
}

existing_container="$(docker compose ps -a -q proxy 2>/dev/null | head -n 1)"
port_binding="80/tcp"
if [[ -z "$existing_container" ]]; then
  existing_container="$(docker compose ps -a -q web 2>/dev/null | head -n 1)"
  port_binding="3000/tcp"
fi
web_port=""
if [[ -n "$existing_container" ]]; then
  existing_port="$(docker inspect --format "{{with (index .HostConfig.PortBindings \"$port_binding\")}}{{(index . 0).HostPort}}{{end}}" "$existing_container" 2>/dev/null || true)"
  running="$(docker inspect --format '{{.State.Running}}' "$existing_container" 2>/dev/null || true)"
  if [[ "$existing_port" =~ ^[0-9]+$ ]] \
    && (( existing_port >= 10100 && existing_port <= 10110 )) \
    && { [[ "$running" == "true" ]] || ! port_in_use "$existing_port"; }; then
    web_port="$existing_port"
  fi
fi

if [[ -z "$web_port" ]]; then
  for candidate in $(seq 10100 10110); do
    if ! port_in_use "$candidate"; then
      web_port="$candidate"
      break
    fi
  done
fi

if [[ -z "$web_port" ]]; then
  echo "Ports 10100–10110 are all occupied. Free one and run ./run.sh again." >&2
  exit 1
fi

export WEB_PORT="$web_port"
export HTTP_PORT="$web_port"
echo "Starting RepoTrajectory on the first available app port: $WEB_PORT"
docker compose up -d --build --remove-orphans

app_url="http://localhost:$WEB_PORT"
if command -v curl >/dev/null 2>&1; then
  ready="false"
  for _ in $(seq 1 90); do
    if curl -fsS "$app_url/collection" >/dev/null 2>&1; then
      ready="true"
      break
    fi
    sleep 1
  done
  if [[ "$ready" != "true" ]]; then
    echo "Containers started, but the web health check timed out." >&2
    docker compose ps >&2
    docker compose logs --tail=80 api web >&2
    exit 1
  fi
fi

echo
echo "RepoTrajectory is ready."
echo "App:        $app_url"
echo "Collection: $app_url/collection"
echo "Admin:      $app_url/admin"
echo "API docs:   $app_url/backend/docs"
echo
echo "Stop everything with: ./run.sh down"
