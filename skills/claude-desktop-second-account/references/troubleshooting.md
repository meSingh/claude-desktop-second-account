# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Second instance opens already signed in to the first account | Profile flag not applied: the app copy was opened directly (Dock pin of the running icon, Spotlight hit on the copy) instead of via the launcher | Open from the launcher. Unpin the running icon and pin the launcher. |
| Clicking the launcher just focuses the first instance | Same as above, or the second instance was started without `--user-data-dir` and hit the app's single-instance lock | Quit the copy (⌘Q in its window), open the launcher. |
| Dock shows two identical orange icons | Launcher points at `/Applications/Claude.app` (older setup), or the copy's custom icon was dropped by an update and the app was relaunched by the updater | `setup_instance.sh --status`; open via the launcher (restores icon); optionally `--install-watcher`. |
| Launcher in Finder still shows the default script icon | Icon cache | `touch` the launcher; `killall Dock` (harmless, Dock restarts) |
| Sign-in in the browser lands in the other instance | Both instances register the same `claude://` handler | Use the email code sign-in, or quit the other instance just for sign-in |
| Keychain prompt "Claude wants to use Claude Safe Storage" | The copy is a different path than the original | Always Allow (one time) |
| `~/.claude-<name>` stays empty after using the Code tab | `CLAUDE_CONFIG_DIR` not passed: launched other than via the launcher, or a very old macOS `open` without `--env` (macOS 13+ needed) | Open via the launcher; check `sw_vers` |
| Skills missing in the second instance after migration | Skills were relative symlinks (e.g. `../../.agents/skills/x`) copied verbatim | `migrate_code_history.py` re-points them; for manual copies use `ln -s "$(realpath old_link)" new_link` |
| Memory from one account shows up in the other | A plugin with a machine-wide store (e.g. claude-mem) enabled in both | Disable it in one instance's `settings.json` |
| Copy is older than the real app / or newer | Copy auto-updates itself; real app updates on its own schedule | Launcher re-clones only when the real app is newer; never downgrades. Either way is fine. |

## Removing everything by hand

```bash
rm -rf "/Applications/<Name>.app" "$HOME/Library/Application Support/<Name>-App"
# only if the user wants that account's local data gone:
rm -rf "$HOME/Library/Application Support/<Name>" "$HOME/.claude-<name>"
launchctl bootout gui/$(id -u)/local.<slug>.iconwatch 2>/dev/null; rm -f ~/Library/LaunchAgents/local.<slug>.iconwatch.plist
```

## Why not the alternatives

- **Editing Claude.app's Info.plist / icon and re-signing**: breaks Anthropic's code signature, Keychain access groups and auto-update, and modifies their app.
- **Separate macOS user account**: works and is the most isolated, but you can't use both side by side in one session.
- **Browser for the second account**: fine for chat, but loses the Code tab, desktop MCP servers and extensions.
