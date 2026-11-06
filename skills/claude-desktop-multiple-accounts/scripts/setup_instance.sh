#!/bin/bash
# Set up, inspect, or remove an extra Claude desktop instance on macOS.
#
#   setup_instance.sh --name NAME [--icon FILE.icns] [--config-dir DIR] [--apps-dir DIR] [--no-link] [--yes]
#   setup_instance.sh --name NAME --status
#   setup_instance.sh --name NAME --link [--yes]
#   setup_instance.sh --name NAME --install-watcher [--yes]
#   setup_instance.sh --name NAME --uninstall [--purge] [--yes]
#
# Setup links the instance's Code config to ~/.claude (skills, rules, hooks,
# plugins, settings, MCP servers) unless --no-link; --link does it for an
# existing instance. Without --yes nothing is changed: the script prints
# exactly what it would do.
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE="$SKILL_DIR/assets/launch.sh.template"
LINKER="$SKILL_DIR/scripts/link_shared.py"
SRC_APP="/Applications/Claude.app"

NAME="" ICON="" CONFIG="" APPS_DIR="" YES=0 MODE=setup PURGE=0 FORCE=0 LINK=1
while [ $# -gt 0 ]; do
  case "$1" in
    --name) NAME="$2"; shift 2 ;;
    --icon) ICON="$2"; shift 2 ;;
    --config-dir) CONFIG="$2"; shift 2 ;;
    --apps-dir) APPS_DIR="$2"; shift 2 ;;
    --yes) YES=1; shift ;;
    --force) FORCE=1; shift ;;
    --status) MODE=status; shift ;;
    --link) MODE=link; shift ;;
    --no-link) LINK=0; shift ;;
    --install-watcher) MODE=watcher; shift ;;
    --uninstall) MODE=uninstall; shift ;;
    --purge) PURGE=1; shift ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

[ -n "$NAME" ] || { echo "--name is required" >&2; exit 2; }
[[ "$NAME" =~ ^[A-Za-z0-9][A-Za-z0-9._\ -]*$ ]] || { echo "Name may use letters, digits, space, dot, dash, underscore" >&2; exit 2; }
[ "$NAME" != "Claude" ] || { echo "Pick a name other than 'Claude' so it can't collide with the real app" >&2; exit 2; }

SLUG="$(printf '%s' "$NAME" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9' '-' | sed 's/--*/-/g; s/^-//; s/-$//')"
[ -n "$CONFIG" ] || CONFIG="$HOME/.claude-${SLUG#claude-}"
if [ -z "$APPS_DIR" ]; then
  # Reuse wherever an existing launcher lives (users often move it), else prefer /Applications.
  if [ -d "/Applications/$NAME.app" ]; then APPS_DIR=/Applications
  elif [ -d "$HOME/Applications/$NAME.app" ]; then APPS_DIR="$HOME/Applications"
  elif [ -w /Applications ]; then APPS_DIR=/Applications
  else APPS_DIR="$HOME/Applications"; fi
fi
LAUNCHER="$APPS_DIR/$NAME.app"
PROFILE="$HOME/Library/Application Support/$NAME"
CLONE_DIR="$HOME/Library/Application Support/${NAME}-App"
CLONE="$CLONE_DIR/$NAME.app"
AGENT_LABEL="local.${SLUG}.iconwatch"
AGENT="$HOME/Library/LaunchAgents/$AGENT_LABEL.plist"

say() { printf '%s\n' "$*"; }
run() { if [ $YES -eq 1 ]; then "$@"; else printf '  would run: %s\n' "$*"; fi; }
is_running() { /usr/bin/pgrep -f "$CLONE/Contents/MacOS/Claude" >/dev/null; }
link_shared() {
  # The app rewrites .claude.json and its desktop config while open, so MCP
  # servers are merged only when it's closed; the launcher merges them on the next start.
  local args=(--to "$CONFIG" --profile "$PROFILE")
  is_running && args+=(--no-mcp)
  [ $YES -eq 1 ] && args+=(--yes)
  /usr/bin/python3 -I "$LINKER" "${args[@]}"
}

case "$MODE" in
status)
  say "Instance:   $NAME"
  say "Launcher:   $LAUNCHER $([ -d "$LAUNCHER" ] && echo '(present)' || echo '(missing)')"
  say "App copy:   $CLONE $([ -f "$CLONE/Contents/Info.plist" ] && echo "(v$(/usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "$CLONE/Contents/Info.plist" 2>/dev/null))" || echo '(not created yet; made on first launch)')"
  say "  icon set: $([ -e "$CLONE/Icon"$'\r' ] && echo yes || echo no)"
  say "Real app:   $SRC_APP (v$(/usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "$SRC_APP/Contents/Info.plist" 2>/dev/null || echo '?'))"
  say "Profile:    $PROFILE $([ -d "$PROFILE" ] && echo '(present)' || echo '(missing)')"
  say "Code config: $CONFIG $([ -f "$CONFIG/.claude.json" ] && echo '(in use)' || echo '(not used yet: open a Code session in this instance)')"
  say "Running:    $(/usr/bin/pgrep -f "$CLONE/Contents/MacOS/Claude --" >/dev/null && echo yes || echo no)"
  say "Shared:     $([ -L "$CONFIG/skills" ] && echo "linked to $(dirname "$(readlink "$CONFIG/skills")") (skills, rules, plugins, settings, Code and desktop MCP)" || echo 'not linked (run with --link)')"
  say "Watcher:    $([ -f "$AGENT" ] && echo installed || echo 'not installed (optional)')"
  exit 0 ;;

link)
  [ -d "$CONFIG" ] || { echo "$CONFIG not found. Set up the instance first." >&2; exit 1; }
  link_shared
  if [ -d "$LAUNCHER" ] && ! grep -q link_shared.py "$LAUNCHER/Contents/Resources/launch.sh" 2>/dev/null; then
    say "Note: this launcher predates linking, so it won't keep settings and MCP servers in sync."
    say "      Rebuild it with: setup_instance.sh --name \"$NAME\" --config-dir \"$CONFIG\" --icon <icns> --force --yes"
  fi
  exit 0 ;;

watcher)
  [ -d "$LAUNCHER" ] || { echo "Set up the instance first." >&2; exit 1; }
  say "Installs a LaunchAgent that restores the custom icon whenever an update replaces the app copy."
  say "  $AGENT"
  if [ $YES -eq 1 ]; then
    mkdir -p "$HOME/Library/LaunchAgents"
    cat > "$AGENT" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$AGENT_LABEL</string>
  <key>ProgramArguments</key><array>
    <string>/bin/bash</string><string>$LAUNCHER/Contents/Resources/launch.sh</string><string>--icon-only</string>
  </array>
  <key>WatchPaths</key><array><string>$CLONE_DIR</string></array>
  <key>ThrottleInterval</key><integer>10</integer>
</dict></plist>
EOF
    plutil -lint "$AGENT" >/dev/null
    launchctl bootout "gui/$(id -u)/$AGENT_LABEL" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$AGENT"
    say "Watcher installed."
  else say "(dry run: add --yes to install)"; fi
  exit 0 ;;

uninstall)
  say "Will remove:"
  say "  $LAUNCHER"; say "  $CLONE_DIR"; [ -f "$AGENT" ] && say "  $AGENT"
  if [ $PURGE -eq 1 ]; then
    say "  $PROFILE   <- login, chats cache, settings, MCP config for this instance"
    say "  $CONFIG    <- Claude Code history, memory, settings for this instance"
  else
    say "Keeping profile and Code config (add --purge to delete them too):"; say "  $PROFILE"; say "  $CONFIG"
  fi
  if /usr/bin/pgrep -f "$CLONE/Contents/MacOS/Claude" >/dev/null; then echo "Quit $NAME first." >&2; exit 1; fi
  if [ $YES -eq 1 ]; then
    [ -f "$AGENT" ] && { launchctl bootout "gui/$(id -u)/$AGENT_LABEL" 2>/dev/null || true; rm -f "$AGENT"; }
    rm -rf "$LAUNCHER" "$CLONE_DIR"
    [ $PURGE -eq 1 ] && rm -rf "$PROFILE" "$CONFIG"
    say "Removed."
  else say "(dry run: add --yes to remove)"; fi
  exit 0 ;;
esac

# ---- setup ----
[ "$(uname)" = Darwin ] || { echo "macOS only." >&2; exit 1; }
[ -d "$SRC_APP" ] || { echo "Claude.app not found in /Applications." >&2; exit 1; }
[ -f "$TEMPLATE" ] || { echo "Missing $TEMPLATE" >&2; exit 1; }
[ -z "$ICON" ] || [ -f "$ICON" ] || { echo "Icon not found: $ICON" >&2; exit 1; }
if [ -d "$LAUNCHER" ] && [ $FORCE -eq 0 ]; then
  echo "$LAUNCHER already exists. Re-run with --force to rebuild the launcher (profile and history are kept)." >&2; exit 1
fi

say "Plan for '$NAME':"
say "  launcher      $LAUNCHER"
say "  profile       $PROFILE"
say "  code config   $CONFIG"
say "  app copy      $CLONE  (created on first launch, APFS clone of $SRC_APP)"
ICON_DESC="$ICON"; [ -n "$ICON_DESC" ] || ICON_DESC="default Claude icon (no custom icon given)"
say "  icon          $ICON_DESC"
say "  shared setup  $([ $LINK -eq 1 ] && echo "linked to ~/.claude, re-synced on every launch" || echo 'not linked (--no-link)')"
[ $YES -eq 1 ] || say "Dry run. Nothing changed. Add --yes to apply."

run mkdir -p "$PROFILE" "$CONFIG" "$APPS_DIR"
run rm -rf "$LAUNCHER"
run osacompile -o "$LAUNCHER" -e 'do shell script quoted form of (POSIX path of (path to me) & "Contents/Resources/launch.sh")'
if [ $YES -eq 1 ]; then
  R="$LAUNCHER/Contents/Resources"; P="$LAUNCHER/Contents/Info.plist"
  N="$NAME" C="$CONFIG" L="$LINK" perl -pe 's/__NAME__/$ENV{N}/g; s/__CONFIG_DIR__/$ENV{C}/g; s/__LINK__/$ENV{L}/g' "$TEMPLATE" > "$R/launch.sh"
  chmod +x "$R/launch.sh"
  [ $LINK -eq 1 ] && cp "$LINKER" "$R/link_shared.py"
  if [ -n "$ICON" ]; then
    cp "$ICON" "$R/applet.icns"
    # osacompile also stores an icon in Assets.car, which macOS prefers; drop it so applet.icns wins.
    /usr/libexec/PlistBuddy -c "Delete :CFBundleIconName" "$P" 2>/dev/null || true
    rm -f "$R/Assets.car"
  else
    cp "$SRC_APP/Contents/Resources/$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIconFile' "$SRC_APP/Contents/Info.plist" | sed 's/\.icns$//').icns" "$R/applet.icns"
  fi
  /usr/libexec/PlistBuddy -c "Set :CFBundleName $NAME" "$P"
  /usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string local.$SLUG.launcher" "$P" 2>/dev/null \
    || /usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier local.$SLUG.launcher" "$P"
  # Editing the bundle invalidates osacompile's ad-hoc signature; re-sign it ad hoc.
  codesign --force --deep -s - "$LAUNCHER" 2>/dev/null
  codesign --verify "$LAUNCHER"
  touch "$LAUNCHER"
  /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$LAUNCHER" 2>/dev/null || true
fi
say
if [ $LINK -eq 1 ]; then link_shared; fi
[ $YES -eq 1 ] && say "Done. Open '$NAME' from $APPS_DIR (or Spotlight) and sign in with the account for this instance."
exit 0
