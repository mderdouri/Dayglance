#!/bin/sh
set -eu

dayglance_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
launcher="$dayglance_dir/launch-dayglance.sh"
if printf '%s' "${XDG_CURRENT_DESKTOP:-}" | grep -qi labwc; then
  autostart_file="$HOME/.config/labwc/autostart"
  mkdir -p "$(dirname -- "$autostart_file")"
  if ! grep -Fq '# Dayglance managed startup' "$autostart_file" 2>/dev/null; then
    quoted_launcher=$(python3 -c 'import shlex,sys; print(shlex.quote(sys.argv[1]))' "$launcher")
    {
      [ ! -s "$autostart_file" ] || printf '\n'
      printf '\n# Dayglance managed startup\n/bin/sh %s &\n' "$quoted_launcher"
    } >> "$autostart_file"
  fi
else
  autostart_dir="$HOME/.config/autostart"
  mkdir -p "$autostart_dir"
  escaped_dayglance_dir=$(printf '%s' "$dayglance_dir" | sed 's/\\/\\\\/g; s/"/\\"/g')
  cat > "$autostart_dir/dayglance.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Dayglance
Comment=Start the Dayglance weather display at desktop login
Exec="/bin/sh" "$escaped_dayglance_dir/launch-dayglance.sh"
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
  chmod 600 "$autostart_dir/dayglance.desktop"
  autostart_file="$autostart_dir/dayglance.desktop"
fi
printf 'Installed the Dayglance desktop login entry at %s\n' "$autostart_file"
printf 'Open Dayglance Settings and enable “Start Dayglance when the desktop logs in”.\n'

