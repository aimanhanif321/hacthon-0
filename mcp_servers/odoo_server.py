"""
Odoo Accounting MCP Server - Exposes Odoo tools via stdin/stdout JSON-RPC protocol.

Tools:
    - create_invoice: Create a customer invoice in Odoo
    - list_invoices: List recent invoices
    - get_invoice: Get invoice details by ID
    - create_payment: Register a payment (flags >$100 per Company Handbook)
    - get_balance: Get current account balances
    - list_journal_entries: List recent journal entries
    - get_profit_loss: Get profit & loss summary

Connects to Odoo hosted on Azure Container Instances via XML-RPC.
Database hosted on Neon DB (cloud PostgreSQL).

Usage:
    python -m mcp_servers.odoo_server

Configure in .claude/mcp.json to use with Claude Code.
"""

import os
import sys
import json
import logging
import xmlrpc.client
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv(override=True)

# Add parent to path so we can import utils
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.retry import retry_with_backoff, health

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("OdooMCPServer")

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "odoo-server"
SERVER_VERSION = "0.1.0"


class OdooClient:
    """Thin wrapper around Odoo's XML-RPC API."""

    def __init__(self):
        self.url = os.getenv("ODOO_URL", "http://localhost:8069")
        self.db = os.getenv("ODOO_DB", "ai-employee")
        self.username = os.getenv("ODOO_USERNAME", "admin")
        self.password = os.getenv("ODOO_PASSWORD", "admin")
        self._uid = None

    @retry_with_backoff(max_retries=2, base_delay=2.0)
    def authenticate(self) -> int:
        """Authenticate with Odoo and return user ID."""
        if self._uid is not None:
            return self._uid
        common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")
        self._uid = common.authenticate(self.db, self.username, self.password, {})
        if not self._uid:
            raise ConnectionError("Odoo authentication failed — check credentials.")
        health.record_success("odoo")
        return self._uid

    def _execute(self, model: str, method: str, *args, **kwargs):
        """Call execute_kw on Odoo."""
        uid = self.authenticate()
        models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")
        return models.execute_kw(
            self.db, uid, self.password, model, method, list(args), kwargs
        )

    def search_read(self, model: str, domain: list, fields: list, limit: int = 20, order: str = ""):
        kw = {"fields": fields, "limit": limit}
        if order:
            kw["order"] = order
        return self._execute(model, "search_read", domain, **kw)

    def create(self, model: str, values: dict) -> int:
        result = self._execute(model, "create", [values])
        # Odoo 17 create may return a list of IDs; unwrap to single int
        if isinstance(result, list):
            return result[0]
        return result

    def read(self, model: str, ids: list, fields: list):
        return self._execute(model, "read", ids, fields=fields)


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

_client = OdooClient()


def _is_dry_run() -> bool:
    return os.getenv("DRY_RUN", "true").lower() == "true"


def handle_create_invoice(params: dict) -> dict:
    """Create a customer invoice."""
    partner_name = params.get("customer_name", "")
    lines = params.get("lines", [])
    if not partner_name or not lines:
        return {"error": "Required: customer_name and lines (list of {product, quantity, price})"}

    if _is_dry_run():
        return {"success": True, "dry_run": True, "message": f"[DRY RUN] Would create invoice for {partner_name}"}

    try:
        # Find or create partner
        partners = _client.search_read("res.partner", [["name", "=", partner_name]], ["id"], limit=1)
        if partners:
            partner_id = partners[0]["id"]
        else:
            partner_id = _client.create("res.partner", {"name": partner_name})

        invoice_lines = []
        for ln in lines:
            invoice_lines.append((0, 0, {
                "name": ln.get("product", "Service"),
                "quantity": ln.get("quantity", 1),
                "price_unit": ln.get("price", 0),
            }))

        invoice_id = _client.create("account.move", {
            "move_type": "out_invoice",
            "partner_id": partner_id,
            "invoice_line_ids": invoice_lines,
        })
        health.record_success("odoo")
        return {"success": True, "invoice_id": invoice_id}
    except Exception as e:
        health.record_failure("odoo", str(e))
        return {"error": str(e)}


def handle_list_invoices(params: dict) -> dict:
    """List recent invoices."""
    limit = params.get("limit", 20)
    try:
        invoices = _client.search_read(
            "account.move",
            [["move_type", "in", ["out_invoice", "in_invoice"]]],
            ["name", "partner_id", "amount_total", "state", "invoice_date", "move_type"],
            limit=limit,
            order="create_date desc",
        )
        health.record_success("odoo")
        return {"success": True, "invoices": invoices, "count": len(invoices)}
    except Exception as e:
        health.record_failure("odoo", str(e))
        return {"error": str(e)}


def handle_get_invoice(params: dict) -> dict:
    """Get details of a specific invoice."""
    invoice_id = params.get("invoice_id")
    if not invoice_id:
        return {"error": "Required: invoice_id"}
    try:
        records = _client.read(
            "account.move", [invoice_id],
            ["name", "partner_id", "amount_total", "amount_residual", "state",
             "invoice_date", "invoice_date_due", "move_type", "invoice_line_ids"],
        )
        if not records:
            return {"error": f"Invoice {invoice_id} not found"}
        health.record_success("odoo")
        return {"success": True, "invoice": records[0]}
    except Exception as e:
        health.record_failure("odoo", str(e))
        return {"error": str(e)}


def handle_create_payment(params: dict) -> dict:
    """Register a payment. Flags payments >$100 per Company Handbook."""
    amount = params.get("amount", 0)
    partner_name = params.get("partner_name", "")
    memo = params.get("memo", "")

    if not amount or not partner_name:
        return {"error": "Required: amount and partner_name"}

    if float(amount) > 100:
        return {
            "success": False,
            "needs_approval": True,
            "message": f"Payment of ${amount} to {partner_name} exceeds $100 — requires human approval per Company Handbook.",
        }

    if _is_dry_run():
        return {"success": True, "dry_run": True, "message": f"[DRY RUN] Would register ${amount} payment to {partner_name}"}

    try:
        partners = _client.search_read("res.partner", [["name", "=", partner_name]], ["id"], limit=1)
        partner_id = partners[0]["id"] if partners else _client.create("res.partner", {"name": partner_name})

        payment_id = _client.create("account.payment", {
            "payment_type": "outbound",
            "partner_type": "supplier",
            "partner_id": partner_id,
            "amount": float(amount),
            "ref": memo or f"Payment to {partner_name}",
        })
        health.record_success("odoo")
        return {"success": True, "payment_id": payment_id}
    except Exception as e:
        health.record_failure("odoo", str(e))
        return {"error": str(e)}


def handle_get_balance(params: dict) -> dict:
    """Get current account balances."""
    try:
        accounts = _client.search_read(
            "account.account", [],
            ["code", "name", "current_balance", "account_type"],
            limit=50,
            order="code",
        )
        health.record_success("odoo")
        return {"success": True, "accounts": accounts, "count": len(accounts)}
    except Exception as e:
        health.record_failure("odoo", str(e))
        return {"error": str(e)}


def handle_list_journal_entries(params: dict) -> dict:
    """List recent journal entries."""
    limit = params.get("limit", 20)
    try:
        entries = _client.search_read(
            "account.move",
            [["move_type", "=", "entry"]],
            ["name", "date", "ref", "amount_total", "state"],
            limit=limit,
            order="date desc",
        )
        health.record_success("odoo")
        return {"success": True, "entries": entries, "count": len(entries)}
    except Exception as e:
        health.record_failure("odoo", str(e))
        return {"error": str(e)}


def handle_get_profit_loss(params: dict) -> dict:
    """Simplified profit & loss: sum income vs expense accounts."""
    try:
        income = _client.search_read(
            "account.account",
            [["account_type", "=", "income"]],
            ["name", "current_balance"],
        )
        expense = _client.search_read(
            "account.account",
            [["account_type", "=", "expense"]],
            ["name", "current_balance"],
        )
        total_income = sum(a.get("current_balance", 0) for a in income)
        total_expense = sum(a.get("current_balance", 0) for a in expense)
        health.record_success("odoo")
        return {
            "success": True,
            "total_income": total_income,
            "total_expense": total_expense,
            "net_profit": total_income - total_expense,
            "income_accounts": income,
            "expense_accounts": expense,
        }
    except Exception as e:
        health.record_failure("odoo", str(e))
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# MCP Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "create_invoice",
        "description": "Create a customer invoice in Odoo. Requires customer_name and lines (list of {product, quantity, price}).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "customer_name": {"type": "string", "description": "Customer / partner name"},
                "lines": {
                    "type": "array",
                    "description": "Invoice line items",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product": {"type": "string"},
                            "quantity": {"type": "number"},
                            "price": {"type": "number"},
                        },
                    },
                },
            },
            "required": ["customer_name", "lines"],
        },
    },
    {
        "name": "list_invoices",
        "description": "List recent invoices from Odoo.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max results (default 20)", "default": 20},
            },
        },
    },
    {
        "name": "get_invoice",
        "description": "Get details of a specific invoice by ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "invoice_id": {"type": "integer", "description": "Odoo invoice ID"},
            },
            "required": ["invoice_id"],
        },
    },
    {
        "name": "create_payment",
        "description": "Register a payment. Payments over $100 are flagged for human approval per Company Handbook.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "amount": {"type": "number", "description": "Payment amount in dollars"},
                "partner_name": {"type": "string", "description": "Payee name"},
                "memo": {"type": "string", "description": "Payment reference / memo"},
            },
            "required": ["amount", "partner_name"],
        },
    },
    {
        "name": "get_balance",
        "description": "Get current account balances from Odoo chart of accounts.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_journal_entries",
        "description": "List recent journal entries.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max results (default 20)", "default": 20},
            },
        },
    },
    {
        "name": "get_profit_loss",
        "description": "Get a simplified profit & loss summary (income vs expenses).",
        "inputSchema": {"type": "object", "properties": {}},
    },
]

TOOL_HANDLERS = {
    "create_invoice": handle_create_invoice,
    "list_invoices": handle_list_invoices,
    "get_invoice": handle_get_invoice,
    "create_payment": handle_create_payment,
    "get_balance": handle_get_balance,
    "list_journal_entries": handle_list_journal_entries,
    "get_profit_loss": handle_get_profit_loss,
}


# ---------------------------------------------------------------------------
# JSON-RPC transport (same pattern as email_server.py)
# ---------------------------------------------------------------------------

def send_response(response: dict):
    line = json.dumps(response)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def handle_request(request: dict) -> dict | None:
    method = request.get("method", "")
    req_id = request.get("id")
    params = request.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        handler = TOOL_HANDLERS.get(tool_name)
        if not handler:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({"error": f"Unknown tool: {tool_name}"})}],
                    "isError": True,
                },
            }
        result = handler(tool_args)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": json.dumps(result)}],
                "isError": "error" in result,
            },
        }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def test_connection():
    """Verify connectivity to the Azure-hosted Odoo instance."""
    try:
        client = OdooClient()
        uid = client.authenticate()
        print(f"Connected to Odoo at {client.url} (uid={uid})")
        return True
    except Exception as e:
        print(f"Connection failed: {e}")
        return False


def main():
    logger.info("Odoo MCP Server starting...")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            send_response({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
            continue
        response = handle_request(request)
        if response is not None:
            send_response(response)
    logger.info("Odoo MCP Server stopped.")


if __name__ == "__main__":
    main()
