#!/usr/bin/env python3
"""Record which software produced a campaign, so it can be reproduced later.

Writes PROVENANCE.txt (human) and PROVENANCE.json (machine) into the campaign folder:
  * ResbosFlow git commit / branch / uncommitted files, python version, host, user, date
  * the campaign .ini (sha256; a copy is kept as campaign.ini by run_process.py)
  * per executable: path, sha256, size, mtime, compiler (GCC string in .comment), the HOPPET version embedded in
    the binary (the "Welcome to HOPPET v. X" banner of a static link), and the key shared libraries it resolves
    (LHAPDF with its version, HOPPET, ROOT with its version, BAT, libstdc++, libgfortran) with realpath and sha256
  * the PDF set(s): where it is found along the search path, sha256 of its .info and member 0 (two sets can have the
    same name and different grids -- pp830a016)
  * input folders/files (grids, templates, data tables): sha256 (folders: hash of the sorted file hashes)
  * the module list the jobs load

Usage (also callable by hand on an old campaign):
  provenance.py --dest DIR [--ini F] [--repo DIR] [--exe label=path[;ld=a:b:c]]... [--input label=path]...
                [--pdf name=search:path:list]... [--modules "GCC/13.2.0 ..."] [--note TEXT]
Never fails the caller: every probe that cannot run is recorded as "unknown".
"""
import argparse
import datetime
import getpass
import hashlib
import json
import os
import platform
import re
import socket
import subprocess
import sys

KEY_LIBS = re.compile(r"(LHAPDF|hoppet|libCore|libBAT|libstdc\+\+|libgfortran|libgcc_s)")
HASH_LIBS = re.compile(r"(LHAPDF|hoppet|libCore|libBAT)")


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for b in iter(lambda: f.read(chunk), b""):
                h.update(b)
        return h.hexdigest()
    except OSError:
        return "unknown"


def sha256_tree(path):
    """Hash of a folder: sha256 of the sorted '<relative name> <file sha256>' lines (symlinks followed)."""
    lines = []
    for root, _, files in sorted(os.walk(path, followlinks=True)):
        for fn in sorted(files):
            p = os.path.join(root, fn)
            lines.append(f"{os.path.relpath(p, path)} {sha256(p)}")
    return hashlib.sha256("\n".join(sorted(lines)).encode()).hexdigest(), len(lines)


def run(cmd, cwd=None, env=None, timeout=60):
    try:
        r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
        return r.stdout
    except Exception:
        return ""


def git_info(repo):
    if repo and not os.path.isdir(os.path.join(repo, ".git")):
        rev = os.path.join(repo, "REVISION")       # written by scripts/mkrevision.sh before copying the tree
        if os.path.exists(rev):
            d = dict(l.rstrip("\n").split("=", 1) for l in open(rev) if "=" in l)
            return {"git_commit": d.get("commit", "unknown") + " (from REVISION file)", "git_branch": d.get("branch", "?"),
                    "git_dirty": d.get("dirty", "") not in ("", "0"), "git_dirty_files": [x for x in d.get("dirty_files", "").split(",") if x]}
    if not repo or not os.path.isdir(os.path.join(repo, ".git")):
        return {"git_commit": "unknown (not a git checkout, no REVISION file)"}
    commit = run(["git", "-C", repo, "rev-parse", "HEAD"]).strip() or "unknown"
    branch = run(["git", "-C", repo, "rev-parse", "--abbrev-ref", "HEAD"]).strip() or "unknown"
    dirty = [l[3:] for l in run(["git", "-C", repo, "status", "--porcelain"]).splitlines()]
    return {"git_commit": commit, "git_branch": branch, "git_dirty": bool(dirty), "git_dirty_files": dirty[:30]}


def embedded_hoppet(path):
    try:
        data = open(path, "rb").read()
    except OSError:
        return "unknown"
    m = re.search(rb"HOPPET v\. ([0-9][^\s\x00]*)", data)
    return m.group(1).decode() if m else "not embedded (dynamic link or no banner)"


def compiler_of(path):
    out = run(["readelf", "-p", ".comment", path])
    m = re.search(r"GCC: \([^)]*\) ([0-9.]+)", out)
    return "GCC " + m.group(1) if m else "unknown"


def lib_version(libpath):
    """Version of the package a shared library belongs to (LHAPDF, ROOT, HOPPET), else ''."""
    real = os.path.realpath(libpath)
    base = os.path.basename(real)
    prefix = os.path.dirname(os.path.dirname(real))
    if "LHAPDF" in base:
        v = run([os.path.join(prefix, "bin", "lhapdf-config"), "--version"]).strip()
        return v or "unknown"
    if base.startswith("libCore"):
        v = run([os.path.join(prefix, "bin", "root-config"), "--version"]).strip()
        if v:
            return v
        try:
            t = open(os.path.join(prefix, "include", "RVersion.h")).read()
            n = [re.search(r"ROOT_VERSION_%s\s+(\d+)" % k, t) for k in ("MAJOR", "MINOR", "PATCH")]
            return ".".join(m.group(1) if m else "?" for m in n)
        except OSError:
            return "unknown"
    if "hoppet" in base:
        v = embedded_hoppet(real)
        return v
    return ""


def exe_info(label, path, opts, modules=""):
    """opts: ld = colon-separated library dirs, src = file this one was copied from (its mtime is the build time),
    env = a shell file to source before ldd (e.g. env_getfixed.sh). ldd is run in the job's module environment, because
    outside it libstdc++/libgfortran resolve to the system ones, which is not what the job uses."""
    ld = opts.get("ld", "")
    info = {"label": label, "path": path}
    if not os.path.exists(path):
        info["error"] = "not found"
        return info
    info.update(realpath=os.path.realpath(path), sha256=sha256(path), size=os.path.getsize(path),
                compiler=compiler_of(path), embedded_hoppet=embedded_hoppet(path))
    src = opts.get("src")
    if src and os.path.exists(src):
        info["copied_from"] = os.path.realpath(src)
        info["built"] = datetime.datetime.fromtimestamp(os.path.getmtime(src)).strftime("%F %T")
    else:
        info["built"] = datetime.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%F %T")
    if opts.get("env"):
        pre = f'source "{opts["env"]}" >/dev/null 2>&1; '
    elif modules:
        pre = f"module purge >/dev/null 2>&1; module load {modules} >/dev/null 2>&1; "
    else:
        pre = ""
    if ld:
        pre += f'export LD_LIBRARY_PATH="{ld}:$LD_LIBRARY_PATH"; '
    out = run(["bash", "-lc", pre + f'ldd "{path}"']) if pre else run(["ldd", path])
    libs = []
    for line in out.splitlines():
        m = re.match(r"\s*(\S+)\s*=>\s*(\S+)", line)
        if not m or not KEY_LIBS.search(m.group(1)):
            continue
        entry = {"name": m.group(1), "path": m.group(2)}
        if m.group(2) != "not":
            entry["realpath"] = os.path.realpath(m.group(2))
            entry["version"] = lib_version(m.group(2))
            if HASH_LIBS.search(m.group(1)):
                entry["sha256"] = sha256(m.group(2))
        else:
            entry["path"] = "NOT FOUND"
        libs.append(entry)
    info["libs"] = libs
    return info


def pdf_info(name, search):
    for d in [x for x in search.split(":") if x]:
        s = os.path.join(d, name)
        if os.path.isdir(s):
            members = sorted(f for f in os.listdir(s) if f.endswith(".dat"))
            return {"name": name, "found_in": d, "n_members": len(members),
                    "info_sha256": sha256(os.path.join(s, name + ".info")),
                    "member0_sha256": sha256(os.path.join(s, members[0])) if members else "unknown"}
    return {"name": name, "found_in": "not found along " + search}


def collect(args):
    P = {"generated": datetime.datetime.now().strftime("%F %T"), "host": socket.gethostname(), "user": getpass.getuser(),
         "python": platform.python_version(), "command": " ".join(sys.argv), "note": args.note or ""}
    P["resbosflow"] = git_info(args.repo)
    if args.ini and os.path.exists(args.ini):
        P["campaign_ini"] = {"path": os.path.abspath(args.ini), "sha256": sha256(args.ini)}
    P["modules"] = args.modules or ""
    P["executables"] = []
    for spec in args.exe:
        label, rest = spec.split("=", 1)
        parts = rest.split(";")
        opts = dict(p.split("=", 1) for p in parts[1:] if "=" in p)
        P["executables"].append(exe_info(label, parts[0], opts, args.modules or ""))
    P["pdfs"] = []
    for spec in args.pdf:
        name, search = spec.split("=", 1)
        pi = pdf_info(name, search)
        if not any((q["name"], q.get("found_in")) == (pi["name"], pi.get("found_in")) for q in P["pdfs"]):
            P["pdfs"].append(pi)
    P["inputs"] = []
    for spec in args.input:
        label, path = spec.split("=", 1)
        if os.path.isdir(path):
            h, n = sha256_tree(path)
            P["inputs"].append({"label": label, "path": path, "sha256": h, "files": n})
        elif os.path.exists(path):
            P["inputs"].append({"label": label, "path": path, "sha256": sha256(path)})
        else:
            P["inputs"].append({"label": label, "path": path, "sha256": "not found"})
    return P


def render(P):
    L = ["PROVENANCE -- software and inputs of this campaign", "=" * 50,
         f"generated   : {P['generated']} on {P['host']} by {P['user']} (python {P['python']})",
         f"command     : {P['command']}"]
    g = P["resbosflow"]
    L.append(f"ResbosFlow  : {g.get('git_commit')} ({g.get('git_branch', '?')})" + ("  *** UNCOMMITTED CHANGES: " + ", ".join(g["git_dirty_files"][:8]) if g.get("git_dirty") else ""))
    if "campaign_ini" in P:
        L.append(f"campaign ini: {P['campaign_ini']['path']}  sha256 {P['campaign_ini']['sha256'][:16]}")
    if P["modules"]:
        L.append(f"modules     : {P['modules']}")
    if P["note"]:
        L.append(f"note        : {P['note']}")
    L += ["", "Executables"]
    for e in P["executables"]:
        if "error" in e:
            L.append(f"  {e['label']:12s} {e['path']}  ({e['error']})")
            continue
        L.append(f"  {e['label']:12s} {e['path']}" + (f"   (copied from {e['copied_from']})" if "copied_from" in e else ""))
        L.append(f"               sha256 {e['sha256'][:16]}  {e['size']} B  built {e['built']}  {e['compiler']}  HOPPET in binary: {e['embedded_hoppet']}")
        for l in e["libs"]:
            L.append(f"               {l['name']:24s} {l.get('version', ''):>14s}  {l.get('realpath', l['path'])}" + (f"  sha256 {l['sha256'][:12]}" if "sha256" in l else ""))
    if P["pdfs"]:
        L += ["", "PDF sets"]
        for p in P["pdfs"]:
            L.append(f"  {p['name']:14s} {p.get('found_in')}" + (f"  members {p['n_members']}  .info {p['info_sha256'][:12]}  member0 {p['member0_sha256'][:12]}" if "n_members" in p else ""))
    if P["inputs"]:
        L += ["", "Inputs"]
        for i in P["inputs"]:
            L.append(f"  {i['label']:22s} sha256 {i['sha256'][:16]}" + (f" ({i['files']} files)" if "files" in i else "") + f"  {i['path']}")
    L += ["", "Run-time environment of each job (modules, node, compiler): provenance_runtime.log"]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dest", required=True)
    ap.add_argument("--ini")
    ap.add_argument("--repo")
    ap.add_argument("--exe", action="append", default=[], help="label=path[;ld=colon:lib:dirs][;src=original file][;env=file to source]")
    ap.add_argument("--input", action="append", default=[], help="label=path (file or folder)")
    ap.add_argument("--pdf", action="append", default=[], help="name=colon:separated:LHAPDF:data:dirs")
    ap.add_argument("--modules")
    ap.add_argument("--note")
    a = ap.parse_args()
    P = collect(a)
    os.makedirs(a.dest, exist_ok=True)
    with open(os.path.join(a.dest, "PROVENANCE.json"), "w") as f:
        json.dump(P, f, indent=1)
    with open(os.path.join(a.dest, "PROVENANCE.txt"), "w") as f:
        f.write(render(P))
    print(f"provenance written to {a.dest}/PROVENANCE.txt")


if __name__ == "__main__":
    main()
