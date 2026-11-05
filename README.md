# claude-desktop-second-account

A Claude skill that sets up a **second Claude desktop app on macOS**, so you can run two accounts side by side (for example personal and work). Each one gets its own login, chats, MCP servers, Claude Code history and its own Dock icon.

Community skill. Not made or endorsed by Anthropic.

## What it does

- Builds a launcher (e.g. "Claude Acme") that starts a separate instance with its own profile folder and its own Claude Code config folder (`CLAUDE_CONFIG_DIR`).
- Gives the second instance a distinct Dock icon made from your company logo, without modifying `Claude.app`. Its signature, Keychain access and auto-updates keep working.
- Shares your main Claude Code setup with the new instance: skills, rules and hooks are symlinked to `~/.claude`; settings and MCP servers (Claude Code and desktop) are merged in and re-synced every time the launcher starts it; plugins start as an instant APFS copy. Logins, chats, history and memory stay separate. Pass `--no-link` for a fully independent instance, or `--link` to link one you already have.
- Optionally copies Claude Code history and memory for chosen folders into the second account, and explains how to move Chat Projects.
- Every script previews its changes first and only applies them with `--yes`. Claude asks you before running anything that changes your Mac.

## Install

This skill sets things up on your Mac, so it runs in **Claude Code**: the Code tab in Claude desktop, the `claude` CLI, or the Claude extension in Cursor / VS Code. It won't work from a regular chat on claude.ai or in Claude desktop's Chat tab, because those run skills in a cloud sandbox, not on your Mac.

**One command (recommended):**

```bash
npx skills add meSingh/claude-desktop-second-account -g -a claude-code -y
```

Needs Node.js. Update later with `npx skills update`.

**Or as a Claude Code plugin** (type these in Claude Code; you get updates through `/plugin`):

```
/plugin marketplace add meSingh/claude-desktop-second-account
/plugin install claude-desktop-second-account@mesingh-skills
```

## Use

Start a new Claude Code session and ask something like:

> I want a separate Claude desktop for my work account, with our company logo as the icon.

Claude walks you through it: name, logo, icon preview, setup, first sign-in and checks.

## Requirements

- macOS 13 or later, with Claude desktop installed in `/Applications`
- Python 3 with Pillow for the custom icon (`python3 -m pip install --user pillow`); optional

## Remove the second instance

Ask Claude to remove it, or run the script from the skill folder:

```bash
bash skills/claude-desktop-second-account/scripts/setup_instance.sh --name "Claude Acme" --uninstall          # preview
bash skills/claude-desktop-second-account/scripts/setup_instance.sh --name "Claude Acme" --uninstall --yes    # remove launcher and app copy, keep data
```

Add `--purge` to also delete that instance's login and Claude Code history.

## Uninstall the skill

`npx skills remove claude-desktop-second-account -g`, or `/plugin uninstall claude-desktop-second-account@mesingh-skills`.

## License

MIT
