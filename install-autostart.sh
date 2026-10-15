#!/bin/sh
set -eu

dayglance_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
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
printf 'Installed the Dayglance desktop login entry at %s\n' "$autostart_dir/dayglance.desktop"
printf 'Open Dayglance Settings and enable “Start Dayglance when the desktop logs in”.\n'
