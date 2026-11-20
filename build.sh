#!/bin/sh
# Build and sign the shortcut. Requires macOS with the Shortcuts app
# (the `shortcuts sign` command needs you to be signed in to iCloud).
#
#   ./build.sh          -> "Spotify to YT Music.shortcut"  (the real thing)
#   ./build.sh --test   -> "Spotify to YT Music (Test).shortcut"
#                          headless variant for `shortcuts run`, see README
set -e
cd "$(dirname "$0")"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

if [ "$1" = "--test" ]; then
  name="Spotify to YT Music (Test)"
else
  name="Spotify to YT Music"
fi

python3 build_shortcut.py "$tmp/unsigned.shortcut" "$@"
shortcuts sign --mode anyone --input "$tmp/unsigned.shortcut" --output "$name.shortcut"
echo "signed -> $name.shortcut"
