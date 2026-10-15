#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
test_dir=$(mktemp -d /tmp/dayglance-config-launch.XXXXXX)
test_project="$test_dir/project"
mock_bin="$test_dir/bin"
mkdir -p "$test_project" "$mock_bin"
cp "$project_dir/launch-dayglance.sh" "$project_dir/server.py" "$test_project/"
test_log="$test_dir/browser-args.txt"

cleanup() {
  case "$test_dir" in /tmp/dayglance-config-launch.*) rm -rf -- "$test_dir" ;; esac
}
trap cleanup EXIT HUP INT TERM

if python3 -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8080/api/device-settings", timeout=1)' >/dev/null 2>&1; then
  printf 'PORT_8080_ALREADY_IN_USE\n' >&2
  exit 2
fi

cat > "$mock_bin/chromium" <<'MOCK'
#!/bin/sh
printf '%s\n' "$@" > "$DAYGLANCE_TEST_ARGS"
python3 -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8080/api/device-settings", timeout=2)'
MOCK
chmod 700 "$mock_bin/chromium"

run_launcher() {
  rm -f "$test_log"
  env PATH="$mock_bin:$PATH" XDG_STATE_HOME="$test_dir/state" XDG_DATA_HOME="$test_dir/data" DAYGLANCE_TEST_ARGS="$test_log" sh "$test_project/launch-dayglance.sh"
}

wait_for_server_to_stop() {
  for attempt in 1 2 3 4 5 6 7 8 9 10; do
    if ! python3 -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8080/api/device-settings", timeout=1)' >/dev/null 2>&1; then
      return
    fi
    sleep 1
  done
  printf 'TEST_SERVER_DID_NOT_STOP\n' >&2
  exit 1
}

printf '{"defaultLocation":null,"locations":[],"preferences":{},"startup":{"autoStart":false,"kiosk":true}}\n' > "$test_project/config.json"
run_launcher
[ ! -e "$test_log" ]
printf 'CONFIG_AUTO_START_DISABLED_OK\n'

printf '{"defaultLocation":null,"locations":[],"preferences":{},"startup":{"autoStart":true,"kiosk":false}}\n' > "$test_project/config.json"
run_launcher
grep -Fx -- '--start-maximized' "$test_log" >/dev/null
if grep -Fx -- '--kiosk' "$test_log" >/dev/null; then
  printf 'KIOSK_FLAG_PRESENT_IN_CONFIG_WINDOWED_MODE\n' >&2
  exit 1
fi
printf 'CONFIG_WINDOWED_START_OK\n'
wait_for_server_to_stop

printf '{"autoStart":true,"kiosk":true}\n' > "$test_project/device-settings.json"
run_launcher
grep -Fx -- '--kiosk' "$test_log" >/dev/null
printf 'DEVICE_OVERRIDE_KIOSK_START_OK\n'
wait_for_server_to_stop

printf '{"autoStart":false,"kiosk":false}\n' > "$test_project/device-settings.json"
run_launcher
[ ! -e "$test_log" ]
printf 'DEVICE_OVERRIDE_AUTO_START_OFF_OK\n'
