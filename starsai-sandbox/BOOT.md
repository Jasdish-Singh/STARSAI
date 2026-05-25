# Sandbox Boot Protocol

Master = Claude Opus 4.7 (this assistant).
Workers = Codex MCP (coder), DeepSeek HTTP (reviewer).

## Lifecycle of a spec

1. **Architect (master) drafts spec** → `specs/<id>.md`
   - Sections: Goal, Inputs, Outputs, Acceptance criteria, Constraints.
2. **Dispatch to Codex** → call `mcp__codex__codex` with:
   - working dir = `starsai-sandbox/src/<id>/`
   - prompt = contents of `specs/<id>.md` + "write files in cwd"
3. **Review by DeepSeek** → `py tools/deepseek_review.py <id>` writes `reviews/<id>.md`.
4. **Gate**
   - `PASS` → move `src/<id>/` → `artifacts/<id>/`, append `logs/run.jsonl`.
   - `FAIL` → loop back to step 2 with findings; max 3 retries; else escalate to user.

## Spec id convention

`<NNN>-<kebab-slug>` e.g. `001-route-cache`, `002-stop-detail-skeleton`.

## Log line schema (`logs/run.jsonl`)

```json
{"ts": "ISO8601", "spec": "001-foo", "stage": "draft|code|review|gate|promote", "verdict": "PASS|FAIL|N/A", "notes": "..."}
```

## Hard rules

- Codex never writes outside `src/<id>/`.
- DeepSeek calls only from `tools/deepseek_review.py`.
- Master commits only after PASS gate.
- Secret never lands in repo (`.gitignore` covers `.env*`).
