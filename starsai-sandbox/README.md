# starsai-sandbox

Isolated multi-agent workspace inside STARSAI.

## Agents

| Role       | Engine                  | Mode         |
|------------|-------------------------|--------------|
| Architect  | Claude Opus 4.7 (me)    | master, gate |
| Coder      | Codex CLI (GPT-5.x)     | MCP          |
| Reviewer   | DeepSeek-v4-pro         | HTTP API     |

## Loop

```
specs/{id}.md   architect writes spec
   ↓
src/{id}/       coder writes code via mcp__codex__codex
   ↓
reviews/{id}.md reviewer scores via tools/deepseek_review.py
   ↓
artifacts/      architect promotes on PASS
logs/run.jsonl  every step appended
```

## Layout

- `specs/`     — one markdown per task (spec + acceptance criteria)
- `src/`       — code Codex produces, one subdir per spec
- `reviews/`   — DeepSeek findings, one per src dir
- `artifacts/` — promoted/passed outputs
- `logs/`      — append-only event log
- `tools/`     — orchestrator scripts (deepseek_review.py, run.py)

## Edit scope

All Edit/Write/Bash actions confined to `starsai-sandbox/`.
Outside paths require explicit user approval.

## Secrets

`DEEPSEEK_API_KEY` pulled at runtime from `C:/Users/jasdi/AppData/Local/hermes/.env`.
Never committed to this dir.
