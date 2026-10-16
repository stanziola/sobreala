"""The Dashboard: everything a client works with, behind one entry (octubre de 2026).

Statistics, mail and contacts used to be four rows of the menu, each its own
screen. Now they hang from one tree down the left, Cloudflare style, and what
is picked fills the pane on the right. The addresses did not change
(`/campaigns`, `/contacts`, `/templates`…): only the frame around them.

The tree is drawn from here and not from the template so that the menu, the
landing of `/dashboard` and the highlighted row can never disagree about who
sees what. A row needs its permission, exactly as the old menu rows did;
hiding one is not a permission, and every route still checks its own.
"""

from __future__ import annotations

from typing import Any

from flask import request, url_for

from models import account as accounts

# The statistics sections, in the order the tree lists them. The first one is
# /dashboard itself; the rest are /dashboard/<slug>.
STATS_SECTIONS = ("summary", "opens", "campaigns", "timing", "growth", "quota")

# Which row each screen belongs to. A screen that is not here (the canvas, a
# confirmation) highlights nothing.
ENDPOINT_ROWS = {
    "campaigns.write": "compose",
    "campaigns.index": "bulk",
    "campaigns.edit": "bulk",
    "campaigns.send": "bulk",
    "campaigns.sent_list": "sent",
    "campaigns.run_detail": "sent",
    "campaigns.sender_page": "sender",
    "designs.index": "templates",
    "designs.create": "templates-new",
    "auth.delete_account": "settings-account",
    "contacts.blocked": "suppressions",
    "contacts.remove_suppressed": "suppressions",
}


def stats_url(section: str) -> str:
    """The address of one statistics section, with the filters on.

    Moving from one section to another keeps what was being looked at: the
    period, the tag and the campaign travel in the address.
    """
    kept = {key: request.args[key] for key in ("period", "tag", "campaign")
            if request.args.get(key)}
    if section == STATS_SECTIONS[0]:
        return url_for("auth.panel", **kept)
    return url_for("auth.panel", section=section, **kept)


def here() -> str:
    """The row of the screen being drawn."""
    endpoint = request.endpoint or ""
    if endpoint == "auth.panel":
        return "stats-" + ((request.view_args or {}).get("section") or STATS_SECTIONS[0])
    if endpoint in ENDPOINT_ROWS:
        return ENDPOINT_ROWS[endpoint]
    # Configuración is a branch too (octubre de 2026): each section its row.
    if endpoint == "auth.settings":
        return "settings-" + (request.view_args or {}).get("section", "account")
    # The rest of Contacts (importing, columns, tags, one contact) lives
    # under the list: they are reached from its buttons.
    if endpoint.startswith("contacts."):
        return "contacts"
    return ""


def tree(account: dict | None) -> list[dict[str, Any]]:
    """The branches this account can open, each with its rows.

    A row is {key, label, url}; a row with `rows` of its own is a sub-branch
    (Correos → Enviar). Empty branches are dropped.
    """
    if account is None or accounts.is_admin(account):
        return []

    def can(permission):
        return accounts.can(account, permission)

    branches = []
    if can(accounts.STATS):
        branches.append({
            "key": "stats", "label": "dash_stats", "icon": "_icon-chart.svg",
            "rows": [{"key": "stats-" + one, "label": "dash_stats_" + one,
                      "url": stats_url(one)} for one in STATS_SECTIONS]})

    send = []
    if can(accounts.SEND):
        send.append({"key": "compose", "label": "dash_compose",
                     "url": url_for("campaigns.write")})
    if can(accounts.CAMPAIGNS):
        send.append({"key": "bulk", "label": "dash_bulk",
                     "url": url_for("campaigns.index")})
    if can(accounts.CAMPAIGNS):
        send.append({"key": "sent", "label": "dash_sent",
                     "url": url_for("campaigns.sent_list")})
    if send:
        branches.append({"key": "mail", "label": "dash_mail", "icon": "_icon-send.svg",
                         "rows": [{"key": "send", "label": "dash_send", "rows": send}]})

    # Plantillas, its own branch (octubre de 2026): it was a row of Enviar.
    if can(accounts.DESIGNS):
        branches.append({
            "key": "templates-branch", "label": "dash_templates",
            "icon": "_icon-template.svg",
            "rows": [{"key": "templates", "label": "dash_templates_mine",
                      "url": url_for("designs.index")},
                     {"key": "templates-new", "label": "dash_templates_new",
                      "url": url_for("designs.create")}]})

    if can(accounts.CONTACTS):
        branches.append({
            "key": "contacts-branch", "label": "dash_contacts", "icon": "_icon-people.svg",
            "rows": [
                {"key": "contacts", "label": "dash_contacts_list",
                 "url": url_for("contacts.index")},
                {"key": "suppressions", "label": "dash_contacts_suppressions",
                 "url": url_for("contacts.blocked")}]})

    # Configuración (octubre de 2026): Remitente, which was in Correos, and the
    # account's own sections, the ones this person may open. The admin has no
    # Dashboard and keeps his Configuración as it was.
    from blueprints.auth.routes import SECTION_LABELS, sections_for

    settings = []
    if can(accounts.SEND):
        settings.append({"key": "sender", "label": "dash_sender",
                         "url": url_for("campaigns.sender_page")})
    settings += [{"key": "settings-" + slug, "label": SECTION_LABELS[slug],
                  "url": url_for("auth.settings", section=slug)}
                 for slug in sections_for(account)]
    if settings:
        branches.append({"key": "settings-branch", "label": "dash_settings",
                         "icon": "_icon-gear.svg", "rows": settings})
    for branch in branches:
        _point(branch)
    return branches


def _point(group: dict[str, Any]) -> str:
    """A group's head links to its first row: what opens without JavaScript."""
    for row in group["rows"]:
        if "rows" in row:
            _point(row)
    group["url"] = group["rows"][0]["url"]
    return group["url"]


def holds(row: dict[str, Any], key: str) -> bool:
    """Whether the row, or one under it, is the one being drawn."""
    if row.get("key") == key:
        return True
    return any(holds(one, key) for one in row.get("rows", ()))
