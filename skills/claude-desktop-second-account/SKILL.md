---
name: claude-desktop-second-account
description: Set up a second, fully separate Claude desktop app on macOS so two accounts (typically personal + work) run side by side, each with its own login, chats, MCP config, Claude Code history and a distinct Dock icon. Also moves Claude Code history/memory and Chat Projects between the two. Use this whenever someone wants to run Claude desktop with two accounts at once, separate work and personal Claude, "clone" or "duplicate" the Claude app, get a second Claude in the Dock, stop switching accounts, give the work Claude its own icon, or move their projects/history from one Claude account to the other — even if they don't say "instance" or "profile". macOS only.
---

# Second Claude desktop account (macOS)

Community skill, not made or endorsed by Anthropic.

The Claude desktop app keeps everything account-specific in one profile folder
(`~/Library/Application Support/Claude`) and Claude Code keeps its own state in
`~/.claude`. Starting a second copy of the app pointed at a different profile
folder (`--user-data-dir`) and a different Code config folder
(`CLAUDE_CONFIG_DIR`, an officially documented variable) gives a clean second
instance. Nothing in the real `Claude.app` is modified, so its code signature,
Keychain access and auto-updates keep working.

The one wrinkle is the Dock: two processes of the same app share one Dock icon.
To get a distinct icon, the launcher runs a private APFS clone of `Claude.app`
(near-zero disk) with a Finder custom icon attached to the bundle folder, again
without editing any signed file.

## How to work with the user

This changes apps on their Mac, so explain the method and get a clear yes before
running anything that writes. All scripts are dry-run by default and print
their plan; show it, then rerun with `--yes`. Read-only checks (versions, paths,
`--status`) are fine without asking.

If you are running *inside* the user's existing Claude desktop app, never quit
or kill Claude processes yourself: both instances share the binary name and you
could close the session you're in. Ask the user to press ⌘Q in the right window.

## Workflow

### 1. Gather

- **Instance name**: what shows under the launcher, e.g. `Claude Acme` or `AcmeAI`. Not plain "Claude".
- **Logo** for the icon: ask, or look for one (`mdfind -name <company> | grep -iE '\.(png|svg|icns)$'`; app icons such as `AppIcon*.appiconset/*.png` in their repos are ideal). Show the user what you found before using it.
- Preflight: `ls /Applications/Claude.app`, `sw_vers`, `python3 -c "import PIL"`. If Pillow is missing, ask before installing it (`python3 -m pip install --user pillow`), or skip the custom icon.

### 2. Make the icon

```bash
python3 scripts/make_icon.py --logo LOGO --out /tmp/<name>.icns --preview /tmp/<name>.png [--style logo|mashup] [--bg '#111114']
```

Then view the preview image yourself and show it to the user; nudge colours or
style until they're happy.

- `logo` (default): their logo on a rounded tile. No Anthropic artwork. Use this
  for anything that will be shared.
- `mashup`: Claude's icon, recoloured, with their logo as a corner badge. Popular
  because it still reads as "Claude" at a glance, but it alters Anthropic's logo,
  which Anthropic's trademark guidelines don't allow outside private use. Offer it
  only as a private icon on their own Mac, and say why.

### 3. Set up

```bash
bash scripts/setup_instance.sh --name "<Name>" --icon /tmp/<name>.icns          # dry run
bash scripts/setup_instance.sh --name "<Name>" --icon /tmp/<name>.icns --yes    # apply
```

Creates the launcher `/Applications/<Name>.app` (or `~/Applications`), the
profile folder `~/Library/Application Support/<Name>` and the Code config folder
`~/.claude-<name>`. The app copy is made on first launch. `--force` rebuilds an
existing launcher and keeps the user's data. `--config-dir DIR` picks a different
Code config folder name (e.g. `~/.claude-acme` for `ClaudeAcme`, instead of `~/.claude-claudeacme`).

**Shared setup (on by default).** Setup also links the new Code config to the
main one, `~/.claude`, through `scripts/link_shared.py`, so the instance has the
user's skills, rules, hooks, plugins, settings and MCP servers without copies
going stale:
- Symlinked: `skills/ rules/ hooks/ agents/ commands/ output-styles/ CLAUDE.md`. New skills added to `~/.claude` appear in every linked instance.
- Plugins are seeded, not linked: the instance gets its own `plugins/cache`, `marketplaces/` and plugin lists as an APFS clone of the main ones (near-zero disk), with paths re-pointed, and the merged settings enable the same plugins. Never symlink these: Code rewrites the lists by replacing the file (which silently breaks the link), and each instance's cleanup would delete plugin versions the other still uses. Re-running `--link` on an instance linked by an older version of this script unshares them and restores its own plugin list.
- Kept per instance: `plugins/data`, `plugins/synced` (plugins the account's org pushes), `plugins/store`, history, memory and login.
- Merged, because these files also hold per-account data: `settings.json` takes every key from the main one (main wins, instance-only keys kept, claude-mem left disabled), `.claude.json` gets the user-level `mcpServers` from `~/.claude.json`, and the instance's desktop `claude_desktop_config.json` gets the desktop MCP servers (Settings → Developer) from the main app's profile. Instance-only servers and the app's own preferences are kept.
- The launcher re-runs the link step on every start while the app is closed, so settings and MCP changes in the main setup carry over. MCP servers are never merged while the instance is open (the app rewrites both files), and `.claude.json` only exists after the first Code session, so MCP servers may arrive one launch later.
- Not shared: desktop extensions (Settings → Extensions). Each app installs and tracks its own, so the user reinstalls them in the new instance; `.mcpb` ones need their original file.

**Tell the user what lands where.** The linking covers Claude Code (the Code tab)
and the desktop MCP servers. The Settings → Skills list shows skills saved on
the claude.ai account or provisioned by the org, never `~/.claude/skills`, so it
can look empty in a new instance even though every skill works in Code sessions
(type `/`). Extensions and the Developer page are per app profile and start
empty; if those sections are missing entirely, Developer Mode (Help →
Troubleshooting) may need enabling in that instance.

**Default settings (always applied, linked or not).** Setup and `--link` add the
keys in `assets/default-settings.json` to the instance's `settings.json` when
it hasn't set them. Today that's `"attribution": false`, so Claude Code adds no
Co-Authored-By trailer, PR footer or session link. `false` needs Claude Code
v2.1.281 or later, and an older version skips the whole settings file. The
desktop app bundles a newer one, but check `claude --version` for any terminal
install that reads the same folder (run `claude update` first). On a machine
that must stay older, use `{"commit": "", "pr": "", "sessionUrl": false}`
instead. Add more house defaults to that file.

Use `--no-link` for a fully independent instance, e.g. one for a company whose
policies shouldn't pick up personal skills, hooks or MCP servers. Ask the user
if that might apply. For an instance set up without linking, or before this
step existed: `setup_instance.sh --name "<Name>" --link` (dry run), then
`--yes`. Existing folders with content are moved aside to
`<item>.before-link-<time>`, never deleted. Then rebuild its launcher with
`--force --yes` (same `--icon` and `--config-dir`) so it keeps re-syncing.

### 4. First launch and sign-in

Tell the user:
- Open `<Name>` from Applications or Spotlight. It should show a **sign-in screen**. If it opens already signed in to the first account, the profile flag was ignored: stop and investigate.
- Sign in with the **email code** option if possible. Browser sign-in (Google SSO) returns through a `claude://` link that macOS may hand to the *other* instance. If that happens, quit the first instance during sign-in only.
- Pin the **launcher** to the Dock, not the running icon. "Keep in Dock" on the running icon pins the bare app copy, which opens without the second profile and just focuses the first instance.

### 5. Verify

`bash scripts/setup_instance.sh --name "<Name>" --status`. After the user opens
one Code session in the new instance, `.claude.json` should appear in the
config folder, which shows `CLAUDE_CONFIG_DIR` is respected. `Shared:` should
say linked; after the next quit and relaunch, the MCP servers are merged too.

Expected, not bugs (tell the user up front):
- A "Trust this workspace?" prompt the first time each folder is opened: trust is stored per config folder. A `.claude/settings.local.json` mentioned there lives in the repo itself and is shared by both instances.
- The Dock tooltip still says "Claude": that name is inside the signed app and changing it would break the signature.
- A one-time Keychain prompt for "Claude Safe Storage": choose Always Allow.

### 6. Optional: move work across

Claude Code (local, fully scriptable):
```bash
python3 scripts/migrate_code_history.py --to ~/.claude-<name> --folder ~/path/to/work-repo [--exclude ~/path/to/skip]   # dry run, then --yes
```
Copies session history and memory for those folders, plus global settings,
rules, skills (re-pointing relative symlinks that would otherwise break),
agents and commands. Items already linked by the shared setup are skipped, so
for a linked instance only history and memory are copied. It leaves out plugins with one machine-wide store
(claude-mem), because enabling them in both instances mixes the two accounts'
memory. The code folders themselves don't move; both instances open them in
place. Old sessions won't show in the new app's sidebar, but memory carries
over. Have the user quit the second instance first, or at least not be mid-session.

Chat Projects (server-side, manual): there is no account-to-account transfer and
conversations can't be moved. Options: (a) by hand: copy the Project
instructions, re-upload knowledge files; (b) from the first account,
**Settings → Privacy → Export data**, then convert the export: inspect the zip's
structure first (don't assume the format), pull the Project's instructions and
docs, render its chats as Markdown, and have the user upload them as knowledge
in a new Project. Remind the user that content moved into a company account
falls under that company's admin visibility and policies.

### 7. Optional extras

- **Icon after updates**: the copy auto-updates itself, and an update replaces the bundle and drops the custom icon. The launcher restores it on the next launch. For instant restore, `setup_instance.sh --name "<Name>" --install-watcher --yes` adds a LaunchAgent that watches the copy. Ask first: it's a persistent background item.
- **Remove**: `setup_instance.sh --name "<Name>" --uninstall` (dry run), then `--yes`. Add `--purge` only if the user explicitly wants that instance's login and Code history deleted too.

## Terms and sharing (tell users who ask)

Based on Anthropic's Consumer Terms, Usage Policy and Trademark Guidelines as of
late 2026; not legal advice, and terms change, so check the current versions:
- Running two accounts that are each yours (e.g. personal + employer-provided) on one Mac isn't prohibited. What is prohibited: sharing credentials or making your account available to someone else; using extra accounts to get around a ban or product guardrails.
- This method doesn't decompile, reverse-engineer or modify the app; it runs an unmodified copy with documented options.
- Brand: don't use Anthropic's name or logo in a way that implies affiliation, and don't alter their logo in shared material. That's why the default icon style uses only the user's own logo and nothing Anthropic-made is bundled here.
- Work accounts are also governed by the employer's agreement and policies.

See `references/troubleshooting.md` for failure modes and fixes.
