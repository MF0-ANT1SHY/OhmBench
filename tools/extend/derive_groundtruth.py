#!/usr/bin/env python3
"""Derive root-cause locations (file, class, function, unfixed lines) from a case's fix.patch.

The repair diff is mapped onto the unfixed source state that was built
(``case.json#source.unfixed.ref`` in ``hosts/<app>``). Every changed or
insertion-point line in a code file is attributed to its innermost enclosing
function (``role: primary``); changes outside any function body (imports,
fields, constants) are ``role: related``. The result is the machine-checkable
``root_causes`` list of ``groundtruth.json``. Derived locations are a starting
point: review them, promote/demote roles and add ``aliases`` before publishing.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODE_SUFFIXES = {".ets", ".ts", ".js"}
KEYWORDS = {"if", "for", "while", "switch", "catch", "return", "new", "function", "else",
            "typeof", "await", "super", "this", "import", "export"}
TYPE_RE = re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:declare\s+)?(?:abstract\s+)?"
                     r"(?:@\w+(?:\([^)]*\))?\s+)*(class|struct|interface|namespace|enum)\s+([A-Za-z_$][\w$]*)")
FUNC_RE = re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)\s*[<(]")
METHOD_RE = re.compile(r"^\s*(?:@\w+(?:\([^)]*\))?\s+)*(?:(?:public|private|protected|static|async|override|readonly|get|set)\s+)*"
                       r"([A-Za-z_$][\w$]*)\s*(?:<[^>]*>)?\s*\([^;]*$")
ARROW_RE = re.compile(r"^\s*(?:(?:export|const|let|var|public|private|protected|static|readonly)\s+)*"
                      r"([A-Za-z_$][\w$]*)\s*(?::[^=]+)?=\s*(?:async\s+)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*(?::[^=]+)?=>")


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args]).decode("utf-8", "replace")


def strip_code(line, state):
    """Remove strings and comments; ``state`` carries block-comment/template state."""
    out, i, n = [], 0, len(line)
    while i < n:
        if state["block"]:
            j = line.find("*/", i)
            if j < 0:
                return "".join(out)
            state["block"], i = False, j + 2
            continue
        c = line[i]
        if state["tpl"]:
            if c == "\\":
                i += 2
                continue
            if c == "`":
                state["tpl"] = False
            i += 1
            continue
        if line.startswith("//", i):
            break
        if line.startswith("/*", i):
            state["block"], i = True, i + 2
            continue
        if c in "'\"":
            j = i + 1
            while j < n and line[j] != c:
                j += 2 if line[j] == "\\" else 1
            out.append(c + c)
            i = j + 1
            continue
        if c == "`":
            state["tpl"], i = True, i + 1
            out.append("``")
            continue
        out.append(c)
        i += 1
    return "".join(out)


def scopes(text):
    """Return [(kind, name, start_line, end_line, parent_type)] for types and functions."""
    state = {"block": False, "tpl": False}
    stack, found, depth = [], [], 0
    pending = None
    for no, raw in enumerate(text.splitlines(), 1):
        code = strip_code(raw, state)
        m = TYPE_RE.match(code)
        if m:
            pending = ("type", m.group(2), no)
        else:
            m = FUNC_RE.match(code) or ARROW_RE.match(code)
            if not m:
                mm = METHOD_RE.match(code)
                # A method declaration sits directly in a class/struct body.
                if mm and mm.group(1) not in KEYWORDS and stack and stack[-1][0] == "type" and stack[-1][4] == depth:
                    m = mm
            if m and m.group(1) not in KEYWORDS:
                pending = ("function", m.group(1), no)
        for ch in code:
            if ch == "{":
                depth += 1
                if pending:
                    parent = next((s[1] for s in reversed(stack) if s[0] == "type"), None)
                    stack.append((pending[0], pending[1], pending[2], parent, depth))
                    pending = None
                else:
                    stack.append(("block", None, no, None, depth))
            elif ch == "}":
                if stack:
                    kind, name, start, parent, _ = stack.pop()
                    if kind != "block":
                        found.append((kind, name, start, no, parent))
                depth -= 1
        if pending and code.rstrip().endswith(";"):
            pending = None
    return found


def changed_lines(patch_text):
    """Map code files to change points in the unfixed file.

    A removed/modified line yields ``(line, line)``; an insertion between unfixed
    lines a and a+1 yields ``(a, a + 1)``.
    """
    files, path, old_no, cur = {}, None, 0, None
    for line in patch_text.splitlines():
        if line.startswith("diff --git "):
            path, cur = None, None
        elif line.startswith("--- "):
            p = line[4:].strip()
            path = None if p == "/dev/null" else p[2:] if p.startswith("a/") else p
        elif line.startswith("@@") and path:
            old_no = int(re.match(r"@@ -(\d+)", line).group(1))
            cur = files.setdefault(path, [])
        elif path and cur is not None and line[:1] in "+- ":
            if line.startswith("-"):
                cur.append((old_no, old_no))
                old_no += 1
            elif line.startswith("+"):
                cur.append((old_no - 1, old_no))
            else:
                old_no += 1
    return {p: v for p, v in files.items() if Path(p).suffix in CODE_SUFFIXES and v}


def innermost(found, a, b, kinds=("function", "type")):
    best = None
    for kind in kinds:
        for sc in found:
            if sc[0] == kind and sc[2] <= a and b <= sc[3] and (best is None or sc[2] >= best[2]):
                best = sc
        if best:
            return best
    return None


def derive(case_dir, hosts_root):
    case = json.loads((case_dir / "case.json").read_text())
    repo = hosts_root / Path(case["host_app"]["local_path"]).name
    ref = case["source"]["unfixed"]["ref"]
    patch = (case_dir / "fix.patch").read_text(errors="replace")
    roots = []
    for path, points in changed_lines(patch).items():
        text = git(repo, "show", f"{ref}:{path}")
        found = scopes(text)
        groups = {}
        for a, b in points:
            a, b = max(a, 1), max(b, 1)
            # An insertion directly before/after a function belongs to the scope
            # that contains both neighbouring lines (usually the class body).
            sc = innermost(found, a, b)
            key = (sc[0], sc[1], sc[4]) if sc else (None, None, None)
            g = groups.setdefault(key, {"lines": [], "span": (sc[2], sc[3]) if sc else None})
            g["lines"] += [a] if a == b else [x for x in (a, b) if sc is None or sc[2] <= x <= sc[3]] or [a]
        for (kind, name, parent), g in groups.items():
            entry = {"file": path, "class": None, "symbol": None}
            if kind == "function":
                entry.update({"class": parent, "symbol": name, "kind": "function", "role": "primary"})
            elif kind == "type":
                entry.update({"class": name, "kind": "class_member", "role": "related"})
            else:
                entry.update({"kind": "module", "role": "related"})
            entry["changed_lines"] = [min(g["lines"]), max(g["lines"])]
            if g["span"]:
                entry["scope_lines"] = list(g["span"])
            roots.append(entry)
    roots.sort(key=lambda r: (r["role"] != "primary", r["file"], r["changed_lines"][0]))
    for i, r in enumerate(roots, 1):
        r["id"] = f"RC{i}"
    keys = ("id", "role", "kind", "file", "class", "symbol", "changed_lines", "scope_lines")
    return [{k: r[k] for k in keys if k in r} for r in roots]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cases", nargs="*", help="case ids (default: all)")
    ap.add_argument("--hosts", type=Path, default=ROOT / "hosts", help="reconstructed host repositories")
    ap.add_argument("--print", action="store_true", help="print instead of writing groundtruth.json")
    args = ap.parse_args()
    for case_dir in sorted((ROOT / "cases").iterdir()):
        if not (case_dir / "case.json").exists() or (args.cases and case_dir.name not in args.cases):
            continue
        roots = derive(case_dir, args.hosts)
        if args.print:
            print(case_dir.name, json.dumps(roots, ensure_ascii=False))
            continue
        gt_path = case_dir / "groundtruth.json"
        gt = json.loads(gt_path.read_text()) if gt_path.exists() else {"case": case_dir.name}
        gt["root_causes"] = roots
        gt_path.write_text(json.dumps(gt, indent=2, ensure_ascii=False) + "\n")
        print(f"{case_dir.name}: {len(roots)} root-cause location(s)")


if __name__ == "__main__":
    main()