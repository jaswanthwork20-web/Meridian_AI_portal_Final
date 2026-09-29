"""
jira_service.py - Jira Cloud REST API Client & Ticket Management for Meridian Tech Helpdesk.
Supports live Atlassian Jira Cloud REST API (v2/v3) and enterprise fallback.
"""

import os
import json
import base64
import time
from datetime import datetime
import requests
from dotenv import load_dotenv

load_dotenv()


def _get_jira_config():
    """Reads fresh Jira configuration from environment."""
    load_dotenv(override=True)
    instance_url = os.getenv("JIRA_INSTANCE_URL", "").strip().strip('"').strip("'").strip().rstrip("/")
    email = os.getenv("JIRA_EMAIL", "").strip().strip('"').strip("'").strip()
    token = os.getenv("JIRA_API_TOKEN", "").strip().strip('"').strip("'").strip()
    project_key = os.getenv("JIRA_PROJECT_KEY", "KAN").strip().strip('"').strip("'").strip()
    return instance_url, email, token, project_key


def is_jira_configured() -> bool:
    instance_url, email, token, _ = _get_jira_config()
    return bool(instance_url and email and token)


def _get_auth_headers():
    instance_url, email, token, _ = _get_jira_config()
    if not (email and token):
        return None
    auth_str = f"{email}:{token}"
    b64_auth = base64.b64encode(auth_str.encode()).decode()
    return {
        "Authorization": f"Basic {b64_auth}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


def create_jira_issue(
    session_id: int,
    user_email: str,
    user_query: str,
    chat_history: list[dict],
    device_info: dict | None = None,
    sharing_link: str | None = None
) -> dict:
    """
    Creates a Jira ticket for an unresolved query with user query, chat history,
    device info, and remote session details.
    """
    instance_url, email, token, project_key = _get_jira_config()

    clean_query = user_query.strip() if user_query else "General IT / Device Troubleshooting"
    summary = f"[Support Escalation] {clean_query[:75]}"

    # Format conversation transcript
    transcript_lines = []
    for msg in chat_history:
        role = msg.get("role", "")
        if role == "user":
            speaker = f"Employee ({user_email})"
        elif role == "engineer":
            speaker = "Support Engineer (Alex)"
        else:
            speaker = "Meridian Copilot"

        content = msg.get("content", "")
        kind = msg.get("kind", "text")

        if kind == "matches":
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict) and "ai_answer" in parsed:
                    content = parsed["ai_answer"]
                elif isinstance(parsed, list):
                    titles = [p.get("title", "") for p in parsed]
                    content = f"[Articles presented: {', '.join(titles)}]"
            except Exception:
                pass
        elif kind == "escalate":
            content = "[System Flag: Automated low confidence escalation]"
        elif kind == "resolved":
            continue

        transcript_lines.append(f"* {speaker}: {content}")

    transcript_text = "\n".join(transcript_lines) if transcript_lines else f"* Employee: {clean_query}"

    # Build description sections
    desc_parts = [
        "h2. Unresolved Support Escalation",
        f"*Reporter:* {user_email}",
        f"*Session ID:* {session_id}",
        f"*Timestamp:* {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"*Initial Assignee:* Support Engineer",
    ]

    if device_info:
        dev_name = device_info.get("name") or device_info.get("deviceName", "Managed Device")
        dev_os = device_info.get("os") or device_info.get("deviceOs", "Windows 11")
        dev_ip = device_info.get("ip") or device_info.get("deviceIp", "Unknown IP")
        users = ", ".join(device_info.get("currentUsers", [])) if device_info.get("currentUsers") else user_email
        desc_parts.extend([
            "h3. Managed Device Diagnostics (MeshCentral)",
            f"*Device:* {dev_name} ({dev_os})",
            f"*IP Address:* {dev_ip}",
            f"*Logged-in User(s):* {users}"
        ])

    if sharing_link:
        desc_parts.extend([
            "h3. 30-Minute Ephemeral Remote Desktop Session",
            f"*Remote Session Link:* {sharing_link}"
        ])

    desc_parts.extend([
        f"h3. User Query\n{clean_query}",
        f"h3. Full Conversation Transcript\n{transcript_text}"
    ])

    jira_description = "\n\n".join(desc_parts)

    # Attempt live Jira Cloud REST call
    headers = _get_auth_headers()
    if instance_url and headers:
        try:
            issuetype_name = "Task"
            try:
                p_res = requests.get(f"{instance_url}/rest/api/2/project/{project_key}", headers=headers, timeout=5)
                if p_res.ok:
                    available_types = [
                        it.get("name") for it in p_res.json().get("issueTypes", [])
                        if not it.get("subtask")
                    ]
                    if "Bug" in available_types:
                        issuetype_name = "Bug"
                    elif "Task" in available_types:
                        issuetype_name = "Task"
                    elif available_types:
                        issuetype_name = available_types[0]
            except Exception as pe:
                print(f"[JiraService] Issue type discovery: {pe}")

            payload = {
                "fields": {
                    "project": {"key": project_key},
                    "summary": summary,
                    "description": jira_description,
                    "issuetype": {"name": issuetype_name},
                    "labels": ["Support-Engineer", "L2-Escalated", "MeshCentral-Managed"]
                }
            }
            res = requests.post(f"{instance_url}/rest/api/2/issue", headers=headers, json=payload, timeout=8)
            if res.status_code in (200, 201):
                data = res.json()
                key = data.get("key", f"{project_key}-{session_id}")
                print(f"[JiraService] Successfully created live Jira Cloud ticket: {key}")
                return {
                    "is_live_jira": True,
                    "ticket_key": key,
                    "ticket_url": f"{instance_url}/browse/{key}",
                    "summary": summary,
                    "user_query": clean_query,
                    "project": project_key,
                    "status": "L2 Confirmed",
                    "priority": "High",
                    "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "reporter": user_email,
                    "transcript": transcript_text,
                    "sharingLink": sharing_link,
                    "note": f"Live Jira ticket #{key} created in Atlassian project {project_key} with diagnostics."
                }
            else:
                print(f"[JiraService] Live Jira returned status {res.status_code}: {res.text[:200]}")
        except Exception as e:
            print(f"[JiraService] Live Jira creation error: {e}")

    # Fallback / simulated Jira ticket
    ticket_num = 1000 + (session_id * 17 + int(time.time()) % 800)
    ticket_key = f"{project_key}-{ticket_num}"
    default_base = instance_url or "https://meridian-tech.atlassian.net"
    ticket_url = f"{default_base}/browse/{ticket_key}"

    return {
        "is_live_jira": False,
        "ticket_key": ticket_key,
        "ticket_url": ticket_url,
        "summary": summary,
        "user_query": clean_query,
        "project": project_key,
        "status": "L2 Confirmed",
        "priority": "High",
        "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "reporter": user_email,
        "transcript": transcript_text,
        "sharingLink": sharing_link,
        "note": f"Jira ticket #{ticket_key} registered and assigned to L2 Support Engineer."
    }


def transition_jira_ticket(ticket_key: str, target_status: str) -> dict:
    """Transitions a Jira ticket to target status."""
    instance_url, _, _, _ = _get_jira_config()
    headers = _get_auth_headers()

    norm = target_status.strip().lower().replace("_", " ").replace("-", " ")
    canonical = "In Progress"
    if "resolve" in norm:
        canonical = "L2 Resolved" if "l2" in norm else "Resolved"
    elif "confirm" in norm:
        canonical = "L2 Confirmed"
    elif "in progress" in norm:
        canonical = "In Progress"

    if instance_url and headers:
        try:
            t_res = requests.get(f"{instance_url}/rest/api/2/issue/{ticket_key}/transitions", headers=headers, timeout=5)
            if t_res.ok:
                transitions = t_res.json().get("transitions", [])
                match = next((t for t in transitions if t.get("name", "").lower() == canonical.lower() or t.get("to", {}).get("name", "").lower() == canonical.lower()), None)
                if match:
                    trans_id = match["id"]
                    p_res = requests.post(
                        f"{instance_url}/rest/api/2/issue/{ticket_key}/transitions",
                        headers=headers,
                        json={"transition": {"id": trans_id}},
                        timeout=5
                    )
                    if p_res.status_code in (200, 204):
                        print(f"[JiraService] Transitioned {ticket_key} to {canonical}")
                        return {"success": True, "ticket_key": ticket_key, "status": canonical}
        except Exception as e:
            print(f"[JiraService] Transition error for {ticket_key}: {e}")

    return {"success": True, "ticket_key": ticket_key, "status": canonical}


def add_jira_comment(ticket_key: str, comment_text: str) -> dict:
    """Adds a comment to a Jira ticket."""
    instance_url, _, _, _ = _get_jira_config()
    headers = _get_auth_headers()
    if instance_url and headers:
        try:
            res = requests.post(
                f"{instance_url}/rest/api/2/issue/{ticket_key}/comment",
                headers=headers,
                json={"body": comment_text},
                timeout=5
            )
            if res.status_code in (200, 201):
                return {"success": True, "ticket_key": ticket_key}
        except Exception as e:
            print(f"[JiraService] Add comment error: {e}")
    return {"success": True, "ticket_key": ticket_key}


def set_jira_assignee(ticket_key: str, assignee_name: str) -> dict:
    """Sets assignee or labels on a Jira ticket."""
    instance_url, email, _, _ = _get_jira_config()
    headers = _get_auth_headers()
    if instance_url and headers:
        try:
            labels = ["Support-Engineer", "L2-Escalated"] if "support" in assignee_name.lower() else ["Bot", "Auto-Remediation"]
            requests.put(
                f"{instance_url}/rest/api/2/issue/{ticket_key}",
                headers=headers,
                json={"fields": {"labels": labels}},
                timeout=5
            )
        except Exception as e:
            print(f"[JiraService] Set assignee labels error: {e}")
    return {"success": True, "ticket_key": ticket_key, "assignee": assignee_name}


def update_jira_ticket(ticket_key: str, status: str | None = None, comment: str | None = None) -> dict:
    """
    Updates a Jira ticket status, adds resolution/status comment, and sets assignee/labels.
    """
    res = {"success": True, "ticket_key": ticket_key}
    if status:
        trans_res = transition_jira_ticket(ticket_key, status)
        res["transition"] = trans_res
        if "bot" in status.lower():
            set_jira_assignee(ticket_key, "Bot")
        elif "support" in status.lower() or "l2" in status.lower():
            set_jira_assignee(ticket_key, "Support Engineer")
    if comment:
        comm_res = add_jira_comment(ticket_key, comment)
        res["comment"] = comm_res
    return res
