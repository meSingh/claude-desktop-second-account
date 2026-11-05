#!/usr/bin/env python3
"""Link an instance's Claude Code config to the main one, so skills, rules,
hooks, plugins, settings and MCP servers are shared instead of copied.

Dry run by default.

  link_shared.py --to ~/.claude-acme [--from ~/.claude] [--main-json ~/.claude.json]
                 [--profile "~/Library/Application Support/Acme"]
                 [--main-profile "~/Library/Application Support/Claude"]
                 [--keep-plugin NAME@market] [--no-mcp] [--auto] [--yes]

Linked (symlinks, so later changes in the main setup show up at once):
  skills/ rules/ hooks/ agents/ commands/ output-styles/ CLAUDE.md
Seeded, then kept per instance: plugins/ cache/, marketplaces/,
  installed_plugins.json, known_marketplaces.json start as an APFS clone of the
  main ones (near-zero disk), with paths re-pointed. Plugins can't be symlinked:
  Code rewrites these files by replacing them, and each instance's cleanup
  would delete plugin versions the other still uses. The merged settings.json
  enables the same plugins, and each instance updates its own copies.
Kept per instance (account-specific): plugins/data, plugins/synced, plugins/store,
  history, sessions, memory, login.
Merged (these files also hold per-account data, so they can't be symlinks):
  settings.json   every key from the main settings.json, main wins; keys only
                  the instance has are kept; shared-state plugins left disabled
  .claude.json    mcpServers from the main ~/.claude.json, main wins per server;
                  servers only the instance has are kept.
  claude_desktop_config.json   (with --profile) the desktop app's own MCP
                  servers (Settings > Developer), merged the same way from the
                  main app's profile; the instance's preferences are kept.
  Both MCP merges are skipped with --no-mcp and must not run while the
  instance is open, because the app rewrites these files.
Not shared: desktop extensions (Settings > Extensions). Each app installs and
tracks its own; reinstall them in the instance.

--auto is for the launcher: it never moves an existing folder aside and prints
only what changed. Re-running is safe; finished items are left alone.
"""
import argparse, glob, json, os, shutil, subprocess, sys, time

LINK_ITEMS = ("skills", "rules", "hooks", "agents", "commands", "output-styles", "CLAUDE.md")
# Folders first: the JSON files are re-pointed at the copies.
PLUGIN_SEED = ("cache", "marketplaces", "known_marketplaces.json", "installed_plugins.json")
# Plugins that keep one machine-wide store, which would mix the two accounts'
# data if enabled in both. Left disabled in the instance unless --keep-plugin.
SHARED_STATE_PLUGINS = ("claude-mem@",)


def is_empty(p):
    if os.path.isdir(p):
        return not os.listdir(p)
    if p.endswith("installed_plugins.json"):
        try:
            return not json.load(open(p)).get("plugins")
        except (OSError, ValueError):
            return False
    return os.path.getsize(p) == 0


def plan_link(src, dst, auto):
    """Return (action, note) for making dst a symlink to src, or None if done."""
    if os.path.islink(dst):
        if os.path.realpath(dst) == os.path.realpath(src):
            return None
        return ("relink", f"{dst} -> {src}  (was -> {os.readlink(dst)})")
    if not os.path.lexists(dst):
        return ("link", f"{dst} -> {src}")
    if is_empty(dst):
        return ("replace-empty", f"{dst} -> {src}  (replaces an empty placeholder)")
    if auto:
        return ("skip", f"{dst} has its own content; run link_shared.py without --auto to link it")
    return ("move-aside", f"{dst} -> {src}  (existing content moved to {os.path.basename(dst)}.before-link-<time>)")


def do_link(src, dst, action):
    if action == "skip":
        return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if action == "relink":
        os.remove(dst)
    elif action == "replace-empty":
        shutil.rmtree(dst) if os.path.isdir(dst) else os.remove(dst)
    elif action == "move-aside":
        os.rename(dst, f"{dst}.before-link-{time.strftime('%Y%m%d-%H%M%S')}")
    os.symlink(src, dst)


def plan_seed(src, dst):
    """Return (action, note) for giving the instance its own copy of a plugin item."""
    if os.path.islink(dst):
        # Left by an earlier version of this script that symlinked plugins.
        own = sorted(glob.glob(f"{glob.escape(dst)}.before-link-*"))
        if own and dst.endswith(".json"):
            return ("restore", f"{dst}  (unshared: restores this instance's own copy {os.path.basename(own[-1])})")
        return ("unshare", f"{dst}  (unshared: replaced the symlink with its own copy of {src})")
    if not os.path.lexists(dst) or is_empty(dst):
        return ("seed", f"{dst}  (own copy of {src})")
    return None


def clone(src, dst):
    # APFS clone: instant and near-zero disk until files diverge.
    if os.path.isdir(src):
        if subprocess.run(["/bin/cp", "-cR", src, dst], capture_output=True).returncode != 0:
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst, symlinks=True)
    else:
        shutil.copy2(src, dst)


def do_seed(src, dst, action, main_plugins, inst_plugins):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.islink(dst):
        os.remove(dst)
    elif os.path.isdir(dst):
        shutil.rmtree(dst)
    elif os.path.lexists(dst):
        os.remove(dst)
    if action == "restore":
        os.rename(sorted(glob.glob(f"{glob.escape(dst)}.before-link-*"))[-1], dst)
    else:
        clone(src, dst)
    if dst.endswith(".json"):
        # Point install paths at this instance's own plugin folder.
        with open(dst) as fh:
            text = fh.read()
        fixed = text.replace(json.dumps(main_plugins + "/")[1:-1], json.dumps(inst_plugins + "/")[1:-1])
        if fixed != text:
            with open(dst, "w") as fh:
                fh.write(fixed)


def load(p):
    with open(p) as fh:
        return json.load(fh)


def write_json(p, data):
    # Write next to the file and rename, so a reader never sees half a file.
    tmp = f"{p}.tmp-{os.getpid()}"
    with open(tmp, "w") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, p)


def merged_settings(main, inst, keep):
    out = dict(inst)
    for k, v in main.items():
        if k == "enabledPlugins" and isinstance(v, dict):
            v = {p: on for p, on in v.items() if not p.startswith(SHARED_STATE_PLUGINS) or p in keep}
        out[k] = v
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="src", default="~/.claude")
    ap.add_argument("--to", dest="dst", required=True)
    ap.add_argument("--main-json", default="~/.claude.json", help="main Code config holding user-level MCP servers")
    ap.add_argument("--profile", help="the instance's desktop app profile folder, to share desktop MCP servers")
    ap.add_argument("--main-profile", default="~/Library/Application Support/Claude", help="the main app's profile folder")
    ap.add_argument("--keep-plugin", action="append", default=[])
    ap.add_argument("--no-mcp", action="store_true", help="don't touch the instance's .claude.json or desktop config")
    ap.add_argument("--auto", action="store_true", help="launcher mode: never move content aside, print only changes")
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()

    src, dst = os.path.expanduser(a.src).rstrip("/"), os.path.expanduser(a.dst).rstrip("/")
    if os.path.realpath(src) == os.path.realpath(dst):
        sys.exit("--from and --to are the same folder")
    if not os.path.isdir(src):
        sys.exit(f"{src} not found")

    links = []
    for item in LINK_ITEMS:
        s = os.path.join(src, item)
        if os.path.exists(s):
            links.append((s, os.path.join(dst, item)))

    changes = []
    for s, d in links:
        p = plan_link(s, d, a.auto)
        if p:
            changes.append(("link", s, d) + p)
    main_plugins, inst_plugins = os.path.join(src, "plugins"), os.path.join(dst, "plugins")
    for item in PLUGIN_SEED:
        s, d = os.path.join(main_plugins, item), os.path.join(inst_plugins, item)
        p = plan_seed(s, d) if os.path.exists(s) or os.path.islink(d) else None
        if p:
            changes.append(("plugins", s, d) + p)

    merged = {}  # destination file -> its new contents

    s_set, d_set = os.path.join(src, "settings.json"), os.path.join(dst, "settings.json")
    if os.path.isfile(s_set) and not os.path.islink(d_set):
        inst = load(d_set) if os.path.isfile(d_set) else {}
        new = merged_settings(load(s_set), inst, a.keep_plugin)
        if new != inst:
            merged[d_set] = new
            dropped = [p for p in load(s_set).get("enabledPlugins", {}) if p not in new.get("enabledPlugins", {})]
            note = f"{d_set}  (shared settings from {s_set}"
            note += f"; left disabled: {', '.join(dropped)})" if dropped else ")"
            changes.append(("settings", s_set, d_set, "merge", note))

    def merge_mcp(kind, main_file, inst_file, create):
        servers = (load(main_file).get("mcpServers") or {}) if os.path.isfile(main_file) else {}
        if not servers or not (create or os.path.isfile(inst_file)):
            return
        inst = load(inst_file) if os.path.isfile(inst_file) else {}
        new = dict(inst)
        new["mcpServers"] = {**(inst.get("mcpServers") or {}), **servers}
        if new != inst:
            merged[inst_file] = new
            changes.append((kind, main_file, inst_file, "merge", f"{inst_file}  (MCP servers: {', '.join(servers)})"))

    d_json = os.path.join(dst, ".claude.json")
    if not a.no_mcp:
        # Code creates .claude.json on its first session; never create it here.
        merge_mcp("mcp", os.path.expanduser(a.main_json), d_json, create=False)
        if a.profile:
            main_prof, prof = os.path.expanduser(a.main_profile), os.path.expanduser(a.profile)
            # Only into a profile that exists: setup creates it, and --link on a
            # mistyped name must not leave a stray folder behind.
            if os.path.isdir(prof) and os.path.realpath(main_prof) != os.path.realpath(prof):
                merge_mcp("desktop", os.path.join(main_prof, "claude_desktop_config.json"),
                          os.path.join(prof, "claude_desktop_config.json"), create=True)

    if not a.auto:
        print(f"Share {src} with {dst}\n")
    for kind, s, d, action, note in changes:
        print(f"  {'skip' if action == 'skip' else kind:9} {note}")
    if not a.auto:
        if not changes:
            print("  everything is already linked")
        if a.no_mcp:
            print("  mcp       Code and desktop MCP servers not merged (--no-mcp); the launcher merges them on the next start")
        elif not os.path.isfile(d_json):
            print(f"  mcp       {d_json} doesn't exist yet; it appears after the first Code session, then the launcher merges MCP servers")
    if not a.yes:
        if not a.auto:
            print("\nDry run. Nothing changed. Add --yes to apply.")
        return

    for kind, s, d, action, note in changes:
        if kind == "link":
            do_link(s, d, action)
        elif kind == "plugins":
            do_seed(s, d, action, main_plugins, inst_plugins)
        else:
            # One backup of the instance's own file, taken before the first merge.
            backup = f"{d}.before-link"
            if os.path.isfile(d) and not os.path.exists(backup):
                shutil.copy2(d, backup)
            os.makedirs(os.path.dirname(d), exist_ok=True)
            write_json(d, merged[d])
    if changes and not a.auto:
        print("\nLinked. Start a new Code session in the instance to pick everything up.")


if __name__ == "__main__":
    main()
