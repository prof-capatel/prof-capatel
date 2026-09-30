# Token Optimization & Fast Execution Directives

## 1. Python Environment & Commands
- **Interpreter Path**: Always execute commands using `.\venv\Scripts\python.exe` on Windows. Never call generic `python` or run virtualenv discovery commands.
- **Package Inspection**: Do not run `pip list` or `pip freeze`. All project dependencies are documented in `requirements.txt` and [SKILL.md](file:///d:/Attendance%20System/.agents/skills/attendance-system/SKILL.md).

## 2. File Reading & Code Navigation
- **Targeted Slices**: Never view entire files larger than 150 lines. Always specify `StartLine` and `EndLine` with `view_file`.
- **Targeted Search**: Use `grep_search` with specific query terms and directory scopes (`src/server/routes`, `src/server/static/`, etc.) instead of scanning files manually.
- **Targeted Edits**: Use `replace_file_content` with exact contiguous chunks instead of rewriting entire files.

## 3. Database & Queries
- **Schema Reference**: Do not run `sqlite3` or `PRAGMA table_info` schema inspection queries. Refer directly to the Database Schema Reference table in [SKILL.md](file:///d:/Attendance%20System/.agents/skills/attendance-system/SKILL.md) for table names, foreign keys, and model classes.

## 4. Test Execution
- **Smoke Testing**: Prefer `.\venv\Scripts\python.exe -m pytest tests/test_smoke.py -q --tb=short` for quick, high-confidence verification.
- **Log Conciseness**: Always append `-q --tb=short` to `pytest` commands to minimize terminal log token usage.
- **Post-Test Purge**: Always run `.\venv\Scripts\python.exe scripts/purge_test_records.py` after test runs to clean up temporary test records.

## 5. Deployment & Release
- **Unified Deployment**: Use `.\venv\Scripts\python.exe scripts/deploy.py` for automated pre-flight checks, git commit, push, and remote EC2 synchronization in a single step when instructed by the user.
