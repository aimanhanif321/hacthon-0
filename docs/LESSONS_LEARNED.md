# Lessons Learned

Architecture decisions, challenges, and trade-offs encountered while building the AI Employee.

## Key Architecture Decisions

### 1. Obsidian Vault as State Machine
**Decision**: Use an Obsidian vault with folder-based states (Inbox → Needs_Action → In_Progress → Done) instead of a database.

**Why**: Human-readable, inspectable, version-controllable. The human-in-the-loop can simply drag files between folders in Obsidian. No database admin needed.

**Trade-off**: No ACID transactions. File moves aren't atomic. Acceptable for this workload volume.

### 2. Claude CLI as the "Brain"
**Decision**: Invoke Claude Code CLI via subprocess rather than using the API directly.

**Why**: Claude CLI has built-in MCP server support, tool use, and context management. Using the CLI means our MCP servers "just work" without building a custom tool-use loop.

**Trade-off**: Each invocation is a fresh context (no memory between calls). We compensate by passing relevant context in the prompt.

### 3. Cloud-First for Services (Azure ACI + Neon DB)
**Decision**: Run Odoo on Azure Container Instances and PostgreSQL on Neon DB, rather than local Docker.

**Why**: Limited local disk space. Cloud services are always available, no Docker daemon needed. Neon's free tier is sufficient for the Odoo database.

**Trade-off**: Network latency for Odoo XML-RPC calls. Cold starts on ACI (~30s). Cost if left running. We mitigate with health checks and start/stop scripts.

### 4. MCP over Direct API Calls
**Decision**: Wrap external services (email, Odoo, social media) as MCP servers rather than having Claude call APIs directly.

**Why**: MCP servers provide a clean tool interface that Claude understands natively. They handle authentication, error handling, and DRY_RUN logic in one place.

**Trade-off**: Extra indirection layer. Each MCP server is another process to manage.

### 5. Human-in-the-Loop via File-Based Approval
**Decision**: Sensitive actions create files in `Pending_Approval/`. Humans move files to `Approved/` or `Rejected/`.

**Why**: Dead simple, works with any file manager or Obsidian. No web UI needed. The file IS the audit trail.

**Trade-off**: No notification system — the human must check the folder. Future improvement: add email/Slack notification when approval is needed.

### 6. Ralph Wiggum Loop (Stop Hook)
**Decision**: Use Claude Code's stop hook to keep Claude working through multi-step tasks automatically.

**Why**: Complex tasks (weekly audit, multi-step plans) need Claude to keep running without human prompting at each step.

**Trade-off**: Risk of infinite loops. We mitigate with a hard iteration cap (10) and clear task state management.

## Challenges

### Windows Compatibility
- Claude CLI on Windows requires `claude.cmd` and `shell=True` for subprocess.
- Path handling: always use `Path` objects, never string concatenation.
- File encoding: always specify `encoding="utf-8"` for read/write operations.

### MCP Server Protocol
- MCP uses JSON-RPC over stdin/stdout. Logging MUST go to stderr, or it corrupts the protocol.
- The `notifications/initialized` method expects no response — returning one breaks some clients.

### DRY_RUN Discipline
- Every external action (email, social post, payment) must check `DRY_RUN` before executing.
- Easy to forget in new code. We centralized the check pattern in each skill module.

### OAuth Token Expiry
- LinkedIn and Meta tokens expire (60-90 days). Need periodic refresh.
- Solution: auth helper scripts in `scripts/` directory.

## Cloud vs Local Trade-offs

| Aspect | Local Docker | Cloud (ACI + Neon) |
|--------|-------------|-------------------|
| Setup complexity | Docker Desktop + compose | Azure CLI + Neon signup |
| Disk usage | ~2 GB (Odoo + Postgres) | 0 GB local |
| Always available | Only when Docker runs | Yes (if not stopped) |
| Cost | Free (local compute) | Free tier / pay-per-use |
| Cold start | ~10s | ~30s |
| Network | localhost (fast) | Internet (slower) |
| Debugging | Docker logs locally | `az container logs` |

## What We'd Do Differently

1. **Start with cloud from day one** — we initially planned local Docker, then pivoted to cloud. Starting cloud-first would have saved rework.
2. **Add notifications early** — the approval workflow is silent. Adding email/Slack notifications for pending approvals would improve turnaround time.
3. **Structured logging from the start** — we use JSON logs, but the schema evolved. Defining the schema upfront (via `utils/audit.py`) would have been cleaner.
