#!/usr/bin/env python3
"""Copy Claude Code history, memory and global setup from one config dir to another.

Copies (never moves) so the source account keeps everything. Dry run by default.

  migrate_code_history.py --to ~/.claude-acme --folder ~/code/acme [--folder ...]
                          [--exclude ~/code/acme/side-project] [--from ~/.claude]
                          [--no-global] [--keep-plugin NAME@market] [--yes]

--folder matches that folder and every subfolder Claude Code has history for.
Global setup = settings.json, rules/, skills/, CLAUDE.md, agents/, commands/.
"""
import argparse, json, os, re, shutil, sys, time

# Plugins that keep one machine-wide store, which would mix the two accounts'
# data if enabled in both. Dropped from the copied settings unless --keep-plugin.
SHARED_STATE_PLUGINS = ("claude-mem@",)
GLOBAL_ITEMS = ("rules", "skills", "agents", "commands", "CLAUDE.md")


def encode(path):
    # Claude Code names each project's history folder by its path, with every
    # non-alphanumeric character replaced by "-".
    return re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(os.path.expanduser(path)).rstrip("/"))


def size(p):
    return sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(p) for f in fs if not os.path.islink(os.path.join(r, f)))


def copy_tree_fix_links(src, dst):
    """Copy a folder; re-point relative symlinks so they still resolve from the new location."""
    os.makedirs(dst, exist_ok=True)
    for name in os.listdir(src):
        s, d = os.path.join(src, name), os.path.join(dst, name)
        if os.path.lexists(d):
            continue
        if os.path.islink(s):
            os.symlink(os.path.realpath(s), d)
        elif os.path.isdir(s):
            shutil.copytree(s, d, symlinks=True)
        else:
            shutil.copy2(s, d)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="src", default="~/.claude")
    ap.add_argument("--to", dest="dst", required=True)
    ap.add_argument("--folder", action="append", default=[])
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--no-global", action="store_true")
    ap.add_argument("--keep-plugin", action="append", default=[])
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()

    src, dst = os.path.expanduser(a.src), os.path.expanduser(a.dst)
    if os.path.abspath(src) == os.path.abspath(dst):
        sys.exit("--from and --to are the same folder")
    projects = os.path.join(src, "projects")
    have = sorted(os.listdir(projects)) if os.path.isdir(projects) else []
    excl = {encode(x) for x in a.exclude}
    picked = []
    for f in a.folder:
        e = encode(f)
        picked += [h for h in have if (h == e or h.startswith(e + "-")) and h not in excl
                   and not any(h.startswith(x + "-") for x in excl) and h not in picked]
    if a.folder and not picked:
        print("No Code history found for those folders. Known history folders:")
        print("\n".join("  " + h for h in have))
        sys.exit(1)

    print(f"From {src}\nTo   {dst}\n")
    for h in picked:
        p = os.path.join(projects, h)
        sessions = len([f for f in os.listdir(p) if f.endswith(".jsonl")])
        mem = len(os.listdir(os.path.join(p, "memory"))) if os.path.isdir(os.path.join(p, "memory")) else 0
        print(f"  history  {h}  ({sessions} sessions, {mem} memory files, {size(p) / 1e6:.1f} MB)")
    if not a.no_global:
        for g in GLOBAL_ITEMS:
            if os.path.islink(os.path.join(dst, g)):
                print(f"  global   {g}  (already linked by link_shared.py, not copied)")
            elif os.path.exists(os.path.join(src, g)):
                print(f"  global   {g}" + ("  (symlinks re-pointed)" if g == "skills" else ""))
        if os.path.exists(os.path.join(src, "settings.json")):
            print("  global   settings.json  (without shared-state plugins: "
                  + ", ".join(p + "*" for p in SHARED_STATE_PLUGINS) + ")")
    if not a.yes:
        print("\nDry run. Nothing copied. Add --yes to copy.")
        return

    if os.path.isdir(dst) and os.listdir(dst):
        backup = f"{dst.rstrip('/')}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
        shutil.copytree(dst, backup, symlinks=True)
        print(f"\nBacked up {dst} -> {backup}")
    os.makedirs(os.path.join(dst, "projects"), exist_ok=True)
    for h in picked:
        # Merge, so history the target instance already created is kept.
        copy_tree_fix_links(os.path.join(projects, h), os.path.join(dst, "projects", h))
    if not a.no_global:
        for g in GLOBAL_ITEMS:
            s = os.path.join(src, g)
            if os.path.islink(os.path.join(dst, g)):
                continue  # linked to the main config: copying would write into it
            if os.path.isdir(s):
                copy_tree_fix_links(s, os.path.join(dst, g))
            elif os.path.isfile(s) and not os.path.exists(os.path.join(dst, g)):
                shutil.copy2(s, os.path.join(dst, g))
        s = os.path.join(src, "settings.json")
        d = os.path.join(dst, "settings.json")
        if os.path.isfile(s) and not os.path.exists(d):
            cfg = json.load(open(s))
            plugins = cfg.get("enabledPlugins", {})
            for k in list(plugins):
                if k.startswith(SHARED_STATE_PLUGINS) and k not in a.keep_plugin:
                    plugins.pop(k)
            with open(d, "w") as fh:
                json.dump(cfg, fh, indent=2)
            os.chmod(d, 0o600)
        elif os.path.exists(d):
            print("Kept the existing settings.json in the destination (not overwritten).")
    print("Copied. Restart the target instance to pick up settings.")


if __name__ == "__main__":
    main()
