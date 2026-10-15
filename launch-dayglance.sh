#!/bin/sh
set -eu

dayglance_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
settings_file="$dayglance_dir/device-settings.json"
config_file="$dayglance_dir/config.json"
device_options=$(python3 -c '
import json,sys
def read_object(path):
  try:
    value=json.load(open(path, encoding="utf-8"))
    return value if isinstance(value,dict) else {}
  except (OSError,ValueError,json.JSONDecodeError):
    return {}
result={"autoStart":False,"kiosk":True}
config=read_object(sys.argv[1]).get("startup",{})
override=read_object(sys.argv[2])
for source in (config,override):
  if isinstance(source,dict):
    for key in result:
      if isinstance(source.get(key),bool): result[key]=source[key]
print(str(result["autoStart"]).lower(),str(result["kiosk"]).lower())
' "$config_file" "$settings_file")
set -- $device_options
auto_start=${1:-false}
kiosk=${2:-true}

[ "$auto_start" = true ] || exit 0

state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/dayglance"
profile_dir="${XDG_DATA_HOME:-$HOME/.local/share}/dayglance/chromium-profile"
mkdir -p "$state_dir"
mkdir -p "$profile_dir"
server_pid=
cleanup() {
  if [ -n "$server_pid" ]; then
    kill "$server_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if ! python3 -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8080/api/device-settings", timeout=1)' >/dev/null 2>&1; then
  python3 "$dayglance_dir/server.py" --host 127.0.0.1 --port 8080 >>"$state_dir/server.log" 2>&1 &
  server_pid=$!
  ready=false
  for attempt in 1 2 3 4 5 6 7 8 9 10; do
    if python3 -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8080/api/device-settings", timeout=1)' >/dev/null 2>&1; then
      ready=true
      break
    fi
    sleep 1
  done
  [ "$ready" = true ] || exit 1
fi

browser=$(command -v chromium || command -v chromium-browser || true)
[ -n "$browser" ] || exit 1
if [ "$kiosk" = true ]; then
  "$browser" --user-data-dir="$profile_dir" --kiosk --noerrdialogs --disable-infobars http://localhost:8080
else
  "$browser" --user-data-dir="$profile_dir" --start-maximized http://localhost:8080
fi
