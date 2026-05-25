#!/usr/bin/env python3
"""DeepSeek reviewer. Reads spec + code diff, posts findings to reviews/{id}.md."""
import json, os, pathlib, sys, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
HERMES_ENV = pathlib.Path("C:/Users/jasdi/AppData/Local/hermes/.env")


def load_key() -> str:
    if k := os.environ.get("DEEPSEEK_API_KEY"):
        return k
    for line in HERMES_ENV.read_text().splitlines():
        if line.startswith("DEEPSEEK_API_KEY="):
            return line.split("=", 1)[1].strip()
    sys.exit("DEEPSEEK_API_KEY not found")


def gather(spec_id: str) -> tuple[str, str]:
    spec = (ROOT / "specs" / f"{spec_id}.md").read_text(encoding="utf-8")
    src_dir = ROOT / "src" / spec_id
    parts = []
    for p in sorted(src_dir.rglob("*")):
        if p.is_file() and p.suffix in {".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".json", ".sh"}:
            parts.append(f"--- {p.relative_to(src_dir)} ---\n{p.read_text(encoding='utf-8', errors='replace')}")
    return spec, "\n\n".join(parts)


def review(spec_id: str) -> dict:
    spec, code = gather(spec_id)
    prompt = (
        "You are a strict code reviewer. Check the code against the spec.\n"
        "Output JSON only: {verdict: PASS|FAIL, severity_counts: {p0,p1,p2,p3}, "
        "findings: [{file, line, severity, issue, fix}], summary}\n\n"
        f"SPEC:\n{spec}\n\nCODE:\n{code}"
    )
    body = json.dumps({
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0,
    }).encode()
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {load_key()}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read())
    return json.loads(resp["choices"][0]["message"]["content"])


def write_report(spec_id: str, result: dict) -> pathlib.Path:
    out = ROOT / "reviews" / f"{spec_id}.md"
    out.write_text(
        f"# Review: {spec_id}\n\n"
        f"**Verdict:** {result['verdict']}\n\n"
        f"**Summary:** {result.get('summary', '')}\n\n"
        f"**Severity:** {json.dumps(result.get('severity_counts', {}))}\n\n"
        "## Findings\n\n" + "\n".join(
            f"- `{f.get('file','?')}:{f.get('line','?')}` **{f.get('severity','?')}** — "
            f"{f.get('issue','')}. Fix: {f.get('fix','')}"
            for f in result.get("findings", [])
        ) + "\n",
        encoding="utf-8",
    )
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: deepseek_review.py <spec_id>")
    spec_id = sys.argv[1]
    result = review(spec_id)
    path = write_report(spec_id, result)
    print(json.dumps({"spec_id": spec_id, "verdict": result["verdict"], "report": str(path)}))
