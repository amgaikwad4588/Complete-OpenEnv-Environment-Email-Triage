"""
Deterministic mock tools for the Email Triage environment.
All functions return pre-defined data keyed by input parameters.
No external calls — fully reproducible.
"""
from __future__ import annotations
from typing import Any


# ---------------------------------------------------------------------------
# Mock databases
# ---------------------------------------------------------------------------

ORDER_DB: dict[str, dict[str, Any]] = {
    "92847": {
        "order_id": "92847",
        "status": "delayed",
        "delay_reason": "held at customs - Brisbane Customs Office",
        "estimated_delivery": "2025-03-28",
        "original_estimated_delivery": "2025-03-13",
        "carrier": "FedEx International",
        "tracking_number": "FX9284700123",
        "items": [{"name": "Enterprise Software License", "qty": 1, "price": 599.00}],
        "customer_email": "angry.customer2024@gmail.com",
        "total": 599.00,
    },
    "78432": {
        "order_id": "78432",
        "status": "in_transit",
        "delay_reason": "minor carrier delay, within acceptable range",
        "estimated_delivery": "2025-03-27",
        "carrier": "UPS Ground",
        "tracking_number": "1Z9WR8720342",
        "items": [{"name": "Nova Wireless Headphones (Blue)", "qty": 1, "price": 89.99}],
        "customer_email": "james.chen@gmail.com",
        "total": 89.99,
    },
    "65109": {
        "order_id": "65109",
        "status": "delivered",
        "delivery_date": "2025-03-18",
        "items": [
            {
                "name": "Echo Wired Earbuds (Red)",
                "ordered": "Nova Wireless Headphones (Blue)",
                "wrong_item": True,
            }
        ],
        "return_label_available": True,
        "return_window_expires": "2025-04-18",
        "customer_email": "lucy.patel@hotmail.com",
        "total": 89.99,
    },
    "INV-2024-0892": {
        "order_id": "INV-2024-0892",
        "type": "invoice",
        "line_items": [
            {"description": "Standard Subscription", "amount": 29.00},
            {"description": "Premium API Access", "amount": 50.00},
        ],
        "total": 79.00,
        "api_access_added_date": "2025-01-15",
        "api_access_added_by": "Account upgrade",
        "note": "API access was added when customer enabled integrations on Jan 15th",
    },
}

CUSTOMER_DB: dict[str, dict[str, Any]] = {
    "angry.customer2024@gmail.com": {
        "name": "Marcus Johnson",
        "tier": "premium",
        "customer_since": "2022-01-15",
        "lifetime_value": 3240.00,
        "open_tickets": 0,
        "previous_refunds": 0,
        "notes": "Long-term customer, no previous complaints",
        "account_status": "active",
    },
    "first.time.buyer@outlook.com": {
        "name": "Emily Chen",
        "tier": "standard",
        "customer_since": "2025-02-21",
        "lifetime_value": 299.00,
        "first_purchase": True,
        "previous_refunds": 0,
        "notes": "First-time buyer, purchased Premium Analytics Dashboard",
        "account_status": "active",
    },
    "enterprise.admin@megacorp.com": {
        "name": "IT Admin Team — MegaCorp",
        "tier": "vip",
        "contract_value": 48000,
        "account_manager": "Jessica Wang",
        "account_manager_email": "j.wang@support.company.com",
        "users_count": 200,
        "customer_since": "2021-03-01",
        "account_status": "active",
        "sla_tier": "enterprise",
    },
    "dev.ops@techstartup.io": {
        "name": "DevOps Team — TechStartup",
        "tier": "premium",
        "contract_value": 9600,
        "customer_since": "2023-07-10",
        "api_calls_today": 47823,
        "account_status": "active",
    },
    "ceo.office@fortune500.com": {
        "name": "Executive Office — Fortune500Corp",
        "tier": "vip",
        "contract_value": 240000,
        "account_manager": "Robert Kim",
        "account_manager_email": "r.kim@support.company.com",
        "customer_since": "2019-06-01",
        "sla_tier": "enterprise",
        "sla_uptime_guarantee": "99.95%",
        "account_status": "active",
    },
    "finance@premium-client.com": {
        "name": "Finance Department — Premium Client Co",
        "tier": "premium",
        "billing_cycle": "quarterly",
        "last_invoice_date": "2024-12-31",
        "last_invoice_number": "INV-2024-Q4-0291",
        "pending_invoice": "Q1-2025",
        "customer_since": "2023-01-01",
        "account_status": "active",
    },
    "furious.client@hotmail.com": {
        "name": "David Park",
        "tier": "standard",
        "customer_since": "2023-11-01",
        "lifetime_value": 1200.00,
        "subscription": "Annual Professional",
        "subscription_amount": 1200.00,
        "previous_refunds": 0,
        "previous_complaints": 2,
        "account_status": "active",
    },
    "critical.user@bigenterprise.com": {
        "name": "Operations Team — BigEnterprise",
        "tier": "vip",
        "contract_value": 96000,
        "account_manager": "Sarah Lin",
        "users_count": 150,
        "customer_since": "2020-02-01",
        "sla_tier": "enterprise",
        "account_status": "active",
    },
}

KNOWN_ISSUES_DB: dict[tuple[str, str], dict[str, Any]] = {
    ("sso", "2025-03-24"): {
        "known_issue": True,
        "tracking_id": "BUG-4421",
        "title": "SAML 2.0 assertion validation failure after v3.14.2 update",
        "affected": "All enterprise SAML 2.0 SSO integrations",
        "eta_fix": "2025-03-25 18:00 UTC",
        "workaround": "Use Magic Link login: Settings > Security > Send Magic Link to bypass SSO temporarily",
        "engineer_contact": "oncall-sso@engineering.company.com",
        "internal_only": False,
    },
    ("platform_outage", "2025-03-25"): {
        "known_issue": True,
        "tracking_id": "INC-8892",
        "title": "Platform service degradation — 40% of users affected",
        "root_cause": "Database connection pool exhaustion triggered by a query optimization rollout",
        "affected": "40% of users, primarily dashboard and reporting features",
        "eta_fix": "2025-03-25 12:00 UTC",
        "public_statement": (
            "We are currently experiencing a service disruption affecting some platform features. "
            "Our engineering team is actively working on a resolution. "
            "Estimated resolution time: within 2 hours. We apologize for the inconvenience."
        ),
        "internal_only": True,  # root_cause and 40% figure must NOT be shared externally
    },
}


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------

def lookup_order(order_id: str) -> dict[str, Any]:
    """Look up an order by ID. Returns order status, items, and delivery info."""
    order = ORDER_DB.get(str(order_id).strip())
    if not order:
        return {"found": False, "error": f"Order {order_id} not found in system"}
    return {"found": True, **order}


def get_customer_info(email: str) -> dict[str, Any]:
    """Look up customer account information by email address."""
    customer = CUSTOMER_DB.get(email.strip().lower())
    if not customer:
        return {
            "found": False,
            "error": f"No account found for {email}",
            "suggestion": "May be a new/guest customer",
        }
    return {"found": True, **customer}


def check_refund_eligibility(email: str, purchase_date: str) -> dict[str, Any]:
    """
    Check if a customer is eligible for a refund based on purchase date.
    Uses fixed reference date 2025-03-25 for determinism.
    """
    from datetime import date

    REFERENCE_DATE = date(2025, 3, 25)
    POLICY_DAYS = 30
    GRACE_WINDOW_DAYS = 35

    try:
        purchase = date.fromisoformat(purchase_date[:10])
    except ValueError:
        return {"error": f"Invalid purchase_date format: {purchase_date}. Use YYYY-MM-DD"}

    days = (REFERENCE_DATE - purchase).days
    eligible = days <= POLICY_DAYS
    exception_possible = days <= GRACE_WINDOW_DAYS

    customer = CUSTOMER_DB.get(email.strip().lower(), {})
    first_purchase = customer.get("first_purchase", False)

    return {
        "eligible": eligible,
        "days_since_purchase": days,
        "policy_days": POLICY_DAYS,
        "exception_possible": exception_possible,
        "is_first_purchase": first_purchase,
        "recommended_action": (
            "APPROVE_REFUND"
            if eligible
            else (
                "CONSIDER_GOODWILL_EXCEPTION"
                if exception_possible and first_purchase
                else "DENY_REFUND"
            )
        ),
        "reason": f"{days} days since purchase (policy: {POLICY_DAYS} days)",
        "purchase_amount": 299.00,
        "product": "Premium Analytics Dashboard",
    }


def lookup_known_issues(issue_type: str, date: str) -> dict[str, Any]:
    """
    Look up known engineering issues by type and date.
    Returns public-safe info only (internal details marked separately).
    """
    key = (issue_type.lower().strip(), date.strip()[:10])
    issue = KNOWN_ISSUES_DB.get(key)
    if not issue:
        return {
            "found": False,
            "message": f"No known issues found for type='{issue_type}' on {date}",
        }
    # Always return; caller decides what to share with customers
    return {"found": True, **issue}


def generate_invoice(email: str, period: str) -> dict[str, Any]:
    """
    Generate or retrieve an invoice for a customer.
    For Q1-2025, returns pre-defined invoice data.
    """
    customer = CUSTOMER_DB.get(email.strip().lower(), {})
    if not customer.get("found", True):
        return {"success": False, "error": f"No account for {email}"}

    if "q1" in period.lower() or "2025-q1" in period.lower() or "january" in period.lower():
        return {
            "success": True,
            "invoice_number": "INV-2025-Q1-0347",
            "period": "January 1 – March 31, 2025",
            "customer_email": email,
            "line_items": [
                {"description": "Premium Tier Subscription (3 months)", "amount": 450.00},
            ],
            "total": 450.00,
            "status": "generated",
            "download_url": "https://billing.company.com/invoices/INV-2025-Q1-0347.pdf",
            "sent_to": email,
        }

    return {
        "success": False,
        "error": f"Invoice for period '{period}' not available or not yet generated",
    }


def get_account_details(email: str) -> dict[str, Any]:
    """
    Get full account details including subscription info.
    Alias for get_customer_info with extra billing data.
    """
    result = get_customer_info(email)
    if result.get("found"):
        result["subscription_details"] = {
            "plan": result.get("tier", "standard"),
            "billing_email": email,
            "payment_method": "Visa ending in 4242",
            "next_billing_date": "2025-04-01",
        }
    return result


# ---------------------------------------------------------------------------
# Tool registry — maps tool names to functions + metadata
# ---------------------------------------------------------------------------

TOOL_REGISTRY: dict[str, dict[str, Any]] = {
    "lookup_order": {
        "fn": lookup_order,
        "definition": {
            "name": "lookup_order",
            "description": "Look up an order by order ID to get status, tracking, and delivery info",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "The order ID to look up"}
                },
                "required": ["order_id"],
            },
        },
    },
    "get_customer_info": {
        "fn": get_customer_info,
        "definition": {
            "name": "get_customer_info",
            "description": "Retrieve customer account information by email address",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "Customer's email address"}
                },
                "required": ["email"],
            },
        },
    },
    "check_refund_eligibility": {
        "fn": check_refund_eligibility,
        "definition": {
            "name": "check_refund_eligibility",
            "description": "Check if a customer qualifies for a refund given their purchase date",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string"},
                    "purchase_date": {
                        "type": "string",
                        "description": "Purchase date in YYYY-MM-DD format",
                    },
                },
                "required": ["email", "purchase_date"],
            },
        },
    },
    "lookup_known_issues": {
        "fn": lookup_known_issues,
        "definition": {
            "name": "lookup_known_issues",
            "description": "Look up known engineering issues by type and date",
            "parameters": {
                "type": "object",
                "properties": {
                    "issue_type": {
                        "type": "string",
                        "description": "Type of issue, e.g. 'sso', 'platform_outage', 'api'",
                    },
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                },
                "required": ["issue_type", "date"],
            },
        },
    },
    "generate_invoice": {
        "fn": generate_invoice,
        "definition": {
            "name": "generate_invoice",
            "description": "Generate or retrieve an invoice for a customer for a specified period",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string"},
                    "period": {
                        "type": "string",
                        "description": "Billing period, e.g. 'Q1-2025', 'January 2025'",
                    },
                },
                "required": ["email", "period"],
            },
        },
    },
    "get_account_details": {
        "fn": get_account_details,
        "definition": {
            "name": "get_account_details",
            "description": "Get full account and subscription details for a customer by email",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "Customer's email address"}
                },
                "required": ["email"],
            },
        },
    },
}


def call_tool(tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a tool call by name with the given parameters."""
    entry = TOOL_REGISTRY.get(tool_name)
    if not entry:
        return {
            "error": f"Unknown tool: '{tool_name}'",
            "available_tools": list(TOOL_REGISTRY.keys()),
        }
    try:
        return entry["fn"](**params)
    except TypeError as exc:
        return {"error": f"Invalid parameters for tool '{tool_name}': {exc}"}
