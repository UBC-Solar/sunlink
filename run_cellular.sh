#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"
LOCAL_ENV_FILE="$REPO_ROOT/.env"

RPI_USER="sunlite"
RPI_HOST="100.88.33.33"
RPI_PASSWORD="solarisbest123"
REMOTE_HOME_DIR="/home/sunlite"
REMOTE_REPO_DIR="${REMOTE_HOME_DIR}/sunlite"
REMOTE_CELLULAR_DIR="${REMOTE_REPO_DIR}/src/influx_cellular"
REMOTE_ENV_PATH="${REMOTE_CELLULAR_DIR}/.env"
REMOTE_SERIAL_PORT="/dev/ttyUSB0"

if ! command -v ssh >/dev/null 2>&1; then
  echo "ssh is required but was not found in PATH." >&2
  exit 1
fi

if ! command -v sshpass >/dev/null 2>&1; then
  echo "sshpass is required to auto-enter the Pi password." >&2
  echo "Install it with: sudo apt-get install sshpass" >&2
  exit 1
fi

export SSHPASS="$RPI_PASSWORD"
ssh_cmd=(sshpass -e ssh -o StrictHostKeyChecking=accept-new "$RPI_USER@$RPI_HOST")

if [[ ! -f "$LOCAL_ENV_FILE" ]]; then
  echo "Local environment file not found: $LOCAL_ENV_FILE" >&2
  exit 1
fi

if ! sshpass -e ssh -o BatchMode=no -o ConnectTimeout=5 "$RPI_USER@$RPI_HOST" true >/dev/null 2>&1; then
  echo "Unable to connect to ${RPI_USER}@${RPI_HOST} over SSH." >&2
  echo "Check that the Pi is powered on, connected to the network, and reachable at ${RPI_HOST}." >&2
  exit 1
fi

read_local_env_values() {
  python3 - "$LOCAL_ENV_FILE" <<'PY'
import sys
from pathlib import Path

env_path = Path(sys.argv[1])
if not env_path.exists():
    raise SystemExit(1)

values = {}
for raw_line in env_path.read_text().splitlines():
    line = raw_line.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    key, value = line.split('=', 1)
    key = key.strip()
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    elif value.startswith("'") and value.endswith("'"):
        value = value[1:-1]
    values[key] = value

for key in ("INFLUX_URL", "INFLUX_TOKEN"):
    if not values.get(key):
        raise SystemExit(f"Missing {key} in {env_path}")
    print(f"{key}={values[key]}")
PY
}

write_remote_env() {
  local influx_url="$1"
  local influx_token="$2"

  "${ssh_cmd[@]}" "python3 - '$REMOTE_ENV_PATH' '$influx_url' '$influx_token' <<'PY'
import sys
from pathlib import Path

env_path = Path(sys.argv[1])
url = sys.argv[2]
token = sys.argv[3]

env_path.parent.mkdir(parents=True, exist_ok=True)
example_path = env_path.parent / '.env.example'
if not env_path.exists():
    if example_path.exists():
        env_path.write_text(example_path.read_text())
    else:
        env_path.write_text('')

lines = []
seen_url = False
seen_token = False
for line in env_path.read_text().splitlines():
    if line.startswith('INFLUX_URL='):
        lines.append(f'INFLUX_URL="{url}"')
        seen_url = True
    elif line.startswith('INFLUX_TOKEN='):
        lines.append(f'INFLUX_TOKEN="{token}"')
        seen_token = True
    else:
        lines.append(line)

if not seen_url:
    lines.append(f'INFLUX_URL="{url}"')
if not seen_token:
    lines.append(f'INFLUX_TOKEN="{token}"')

env_path.write_text('\n'.join(lines) + '\n')
PY"
}

check_remote_repo() {
  "${ssh_cmd[@]}" "test -d '${REMOTE_REPO_DIR}' && echo remote_ready" >/dev/null 2>&1 || {
    echo "Remote repo not found at ${REMOTE_REPO_DIR}." >&2
    exit 1
  }
}

check_remote_serial() {
  "${ssh_cmd[@]}" "test -e '${REMOTE_SERIAL_PORT}'" >/dev/null 2>&1 || {
    echo "Serial device ${REMOTE_SERIAL_PORT} was not found on the Pi." >&2
    echo "Connect the USB device or update REMOTE_SERIAL_PORT in the script if needed." >&2
    exit 1
  }
}

mapfile -t local_env_values < <(read_local_env_values)

INFLUX_URL=""
INFLUX_TOKEN=""
for entry in "${local_env_values[@]}"; do
  case "$entry" in
    INFLUX_URL=*)
      INFLUX_URL="${entry#INFLUX_URL=}"
      ;;
    INFLUX_TOKEN=*)
      INFLUX_TOKEN="${entry#INFLUX_TOKEN=}"
      ;;
  esac
done

if [[ -z "$INFLUX_URL" || -z "$INFLUX_TOKEN" ]]; then
  echo "Unable to read INFLUX_URL and INFLUX_TOKEN from $LOCAL_ENV_FILE" >&2
  exit 1
fi

echo "Using INFLUX_URL from local .env: $INFLUX_URL"
echo "Using INFLUX_TOKEN from local .env"

check_remote_repo
check_remote_serial
write_remote_env "$INFLUX_URL" "$INFLUX_TOKEN"

echo "Starting cellular parser on the Pi..."
"${ssh_cmd[@]}" "cd '${REMOTE_REPO_DIR}' && source .venv/bin/activate && cd src/influx_cellular && python3 cell_script.py"
