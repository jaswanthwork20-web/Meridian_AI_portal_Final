"""
escalation_service.py - Real-Time Support Escalation, SSE Streams, and Live Chat Handoff
for Meridian Tech Helpdesk.
"""

import os
import json
import asyncio
import time
import uuid
from datetime import datetime, timedelta
from dotenv import load_dotenv

try:
    from . import meshcentral_service, jira_service
except ImportError:
    import meshcentral_service
    import jira_service

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

ESCALATIONS_FILE = os.path.join(DATA_DIR, "escalations.json")
CONVERSATIONS_FILE = os.path.join(DATA_DIR, "conversations.json")

# In-memory stores
escalation_store: list[dict] = []
conversation_store: dict[str, dict] = {}

# SSE Queues
conversation_subscribers: dict[str, set[asyncio.Queue]] = {}


def save_stores():
    try:
        with open(ESCALATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(escalation_store, f, indent=2)
    except Exception as e:
        print(f"[EscalationService] Error saving escalations: {e}")

    try:
        serialized = []
        for cid, conv in conversation_store.items():
            serialized.append({
                "id": cid,
                "messages": conv.get("messages", []),
                "status": conv.get("status", "active"),
                "title": conv.get("title"),
                "ticketId": conv.get("ticketId"),
                "jiraKey": conv.get("jiraKey"),
                "issueSummary": conv.get("issueSummary"),
                "sharingLink": conv.get("sharingLink"),
                "engineerJoined": conv.get("engineerJoined", False),
                "engineerJoinedAt": conv.get("engineerJoinedAt"),
                "engineerName": conv.get("engineerName"),
                "createdAt": conv.get("createdAt")
            })
        with open(CONVERSATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(serialized, f, indent=2)
    except Exception as e:
        print(f"[EscalationService] Error saving conversations: {e}")


def load_stores():
    global escalation_store, conversation_store
    try:
        if os.path.exists(ESCALATIONS_FILE):
            with open(ESCALATIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    escalation_store.clear()
                    escalation_store.extend(data)
                    print(f"[EscalationService] Loaded {len(escalation_store)} escalations from disk.")
    except Exception as e:
        print(f"[EscalationService] Error loading escalations: {e}")

    try:
        if os.path.exists(CONVERSATIONS_FILE):
            with open(CONVERSATIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    conversation_store.clear()
                    for item in data:
                        cid = str(item.get("id"))
                        conversation_store[cid] = item
                    print(f"[EscalationService] Loaded {len(conversation_store)} conversations from disk.")
    except Exception as e:
        print(f"[EscalationService] Error loading conversations: {e}")


load_stores()


# ---------------- SSE Broadcasts ----------------
async def broadcast_conversation(conv_id: str, payload: dict):
    """Pushes a live event to all clients connected to a specific conversation."""
    cid = str(conv_id)
    subs = conversation_subscribers.get(cid, set())
    msg = f"data: {json.dumps(payload)}\n\n"
    dead = []
    for q in list(subs):
        try:
            await q.put(msg)
        except Exception:
            dead.append(q)
    for q in dead:
        subs.discard(q)


def subscribe_conversation(conv_id: str) -> asyncio.Queue:
    cid = str(conv_id)
    if cid not in conversation_subscribers:
        conversation_subscribers[cid] = set()
    q = asyncio.Queue()
    conversation_subscribers[cid].add(q)
    return q


def unsubscribe_conversation(conv_id: str, q: asyncio.Queue):
    cid = str(conv_id)
    if cid in conversation_subscribers:
        conversation_subscribers[cid].discard(q)


# ---------------- Core Escalation Operations ----------------
async def escalate_session(
    session_id: int,
    user_email: str,
    issue_summary: str,
    execution_details: str = "",
    device_id: str | None = None
) -> dict:
    """
    Escalates an issue to L2 Support:
      1. Generates 30-min MeshCentral remote desktop sharing link
      2. Creates / attaches Jira Cloud ticket in project KAN
      3. Sets ticket to 'L2 Confirmed' assigned to Support Engineer
    4. Links the escalation to the employee conversation
    """
    cid = str(session_id)
    now = datetime.utcnow()
    now_iso = now.isoformat() + "Z"

    # 1. MeshCentral 30-min sharing link
    sharing_info = meshcentral_service.create_device_sharing_link(device_id=device_id, duration_minutes=30)
    sharing_link = sharing_info.get("sharingLink", "")
    expires_at = sharing_info.get("expiresAt", (now + timedelta(minutes=30)).isoformat() + "Z")
    device_name = sharing_info.get("deviceName", "AVDGLS5-4")
    device_os = sharing_info.get("deviceOs", "Microsoft Windows 11 Enterprise")
    device_ip = sharing_info.get("deviceIp", "10.73.87.230")
    current_users = sharing_info.get("currentUsers", ["AzureAD\\SANDEEPDUBEY"])

    # 2. Jira Cloud Ticket
    dev_diag = {
        "name": device_name,
        "os": device_os,
        "ip": device_ip,
        "currentUsers": current_users
    }
    chat_history = []
    if cid in conversation_store:
        chat_history = conversation_store[cid].get("messages", [])

    jira_res = jira_service.create_jira_issue(
        session_id=session_id,
        user_email=user_email,
        user_query=issue_summary,
        chat_history=chat_history,
        device_info=dev_diag,
        sharing_link=sharing_link
    )
    jira_key = jira_res.get("ticket_key", f"KAN-{session_id}")
    jira_url = jira_res.get("ticket_url", f"https://agnishpaul2002.atlassian.net/browse/{jira_key}")

    # 3. Create Ticket Record
    esc_id = f"ESC-{session_id}-{uuid.uuid4().hex[:4].upper()}"
    ticket = {
        "id": esc_id,
        "jiraKey": jira_key,
        "jiraUrl": jira_url,
        "jiraStatus": "L2 Confirmed",
        "deviceId": sharing_info.get("deviceId", "default"),
        "deviceName": device_name,
        "deviceOs": device_os,
        "deviceIp": device_ip,
        "currentUsers": current_users,
        "issueSummary": issue_summary,
        "summary": issue_summary,
        "executionDetails": execution_details or "Remediation session escalated to L2 Support Engineer.",
        "sharingLink": sharing_link,
        "conversationId": cid,
        "status": "new",
        "assignedTo": "Support Engineer",
        "assignee": "Support Engineer",
        "createdAt": now_iso,
        "linkExpiresAt": expires_at,
        "expiresAt": expires_at,
        "resolvedAt": None,
        "notes": ""
    }

    # Add to escalation store
    escalation_store.insert(0, ticket)

    # Update conversation store
    if cid not in conversation_store:
        conversation_store[cid] = {"messages": [], "status": "active", "title": issue_summary}
    conv = conversation_store[cid]
    conv["status"] = "escalated"
    conv["escalatedAt"] = now_iso
    conv["ticketId"] = esc_id
    conv["jiraKey"] = jira_key
    conv["issueSummary"] = issue_summary
    conv["sharingLink"] = sharing_link

    handoff_text = f"Live Handoff Initiated: Issue escalated to L2 Support Engineer (Alex Turner). Jira: {jira_key}."
    conv.setdefault("messages", []).append({
        "id": f"handoff-{cid}-{int(now.timestamp())}",
        "role": "system",
        "kind": "handoff",
        "type": "handoff",
        "content": handoff_text,
        "jiraKey": jira_key,
        "jiraUrl": jira_url,
        "sharingLink": sharing_link,
        "timestamp": now_iso
    })

    save_stores()

    # Broadcast live handoff event to conversation clients (Maya & Alex)
    await broadcast_conversation(cid, {
        "type": "handoff",
        "message": handoff_text,
        "jiraKey": jira_key,
        "sharingLink": sharing_link,
        "time": now_iso
    })

    print(f"[EscalationService] Escalated session #{session_id} -> {jira_key} (Link: {sharing_link[:40]}...)")
    return ticket


async def create_remediation_ticket(
    session_id: int,
    user_email: str,
    issue_summary: str,
    device_info: dict | None = None,
    execution_details: str = "Automated remediation initiated."
) -> dict:
    """
    Creates a Jira ticket and registers it in the escalation/dashboard store BEFORE
    executing an automated remote action (e.g. Zoom cache clear).
    Initial status: 'In Progress', Assignee: 'Bot'.
    """
    cid = str(session_id)
    now = datetime.utcnow()
    now_iso = now.isoformat() + "Z"

    device_name = (device_info or {}).get("name", "AVDGLS5-4")
    device_os = (device_info or {}).get("os", "Microsoft Windows 11 Enterprise")
    device_ip = (device_info or {}).get("ip", "10.73.87.230")
    current_users = (device_info or {}).get("currentUsers", ["AzureAD\\SANDEEPDUBEY"])
    device_id = (device_info or {}).get("id", "default")

    chat_history = []
    if cid in conversation_store:
        chat_history = conversation_store[cid].get("messages", [])

    # Create ticket in Jira Cloud
    jira_res = jira_service.create_jira_issue(
        session_id=session_id,
        user_email=user_email,
        user_query=issue_summary,
        chat_history=chat_history,
        device_info=device_info,
        sharing_link=""
    )
    jira_key = jira_res.get("ticket_key", f"KAN-{session_id}")
    jira_url = jira_res.get("ticket_url", f"https://agnishpaul2002.atlassian.net/browse/{jira_key}")

    # Set initial assignee to Bot in Jira
    jira_service.set_jira_assignee(jira_key, "Bot")

    esc_id = f"ESC-{session_id}-{uuid.uuid4().hex[:4].upper()}"
    ticket = {
        "id": esc_id,
        "jiraKey": jira_key,
        "jiraUrl": jira_url,
        "jiraStatus": "In Progress",
        "status": "In Progress",
        "deviceId": device_id,
        "deviceName": device_name,
        "deviceOs": device_os,
        "deviceIp": device_ip,
        "currentUsers": current_users,
        "issueSummary": issue_summary,
        "summary": issue_summary,
        "executionDetails": execution_details,
        "sharingLink": "",
        "conversationId": cid,
        "assignedTo": "Bot",
        "assignee": "Bot",
        "createdAt": now_iso,
        "linkExpiresAt": None,
        "expiresAt": None,
        "resolvedAt": None,
        "notes": "Automated remote action initiated by Bot."
    }

    escalation_store.insert(0, ticket)

    if cid not in conversation_store:
        conversation_store[cid] = {"messages": [], "status": "active", "title": issue_summary}
    conv = conversation_store[cid]
    conv["ticketId"] = esc_id
    conv["jiraKey"] = jira_key
    conv["issueSummary"] = issue_summary
    save_stores()

    print(f"[EscalationService] Created remediation ticket {esc_id} (Jira: {jira_key})")
    return ticket


async def mark_ticket_bot_resolved(session_id_or_key: str | int, comment: str = "") -> dict:
    """
    Marks a ticket as 'Bot Resolved' across Jira Cloud and local dashboard store.
    Broadcasts the resolution event to the Support Engineer Dashboard.
    """
    cid = str(session_id_or_key)
    local_ticket = next((
        t for t in escalation_store
        if t.get("id") == cid or t.get("jiraKey") == cid or str(t.get("conversationId")) == cid
    ), None)

    target_key = local_ticket.get("jiraKey") if local_ticket else (cid if cid.startswith("KAN-") else None)
    now_iso = datetime.utcnow().isoformat() + "Z"
    resolution_comment = comment or "✅ Issue confirmed resolved by user after automated Bot remediation."

    if target_key:
        jira_service.update_jira_ticket(
            ticket_key=target_key,
            status="Bot Resolved",
            comment=resolution_comment
        )

    if local_ticket:
        local_ticket["status"] = "Bot Resolved"
        local_ticket["jiraStatus"] = "Bot Resolved"
        local_ticket["assignedTo"] = "Bot"
        local_ticket["assignee"] = "Bot"
        local_ticket["resolvedAt"] = now_iso
        local_ticket["notes"] = resolution_comment
    else:
        local_ticket = {
            "id": f"ESC-{cid}",
            "jiraKey": target_key or f"KAN-{cid}",
            "status": "Bot Resolved",
            "jiraStatus": "Bot Resolved",
            "assignedTo": "Bot",
            "assignee": "Bot",
            "notes": resolution_comment,
            "conversationId": cid,
            "createdAt": now_iso,
            "resolvedAt": now_iso
        }
        escalation_store.insert(0, local_ticket)

    if cid in conversation_store:
        conversation_store[cid]["status"] = "resolved"

    save_stores()

    print(f"[EscalationService] Ticket for session/key {cid} marked as 'Bot Resolved'")
    return {"success": True, "status": "Bot Resolved", "jiraKey": target_key}


async def engineer_join_conversation(conv_id: str, engineer_name: str = "Alex (Support Engineer)") -> dict:
    """Announces Support Engineer joining the chat session."""
    cid = str(conv_id)
    if cid not in conversation_store:
        conversation_store[cid] = {"messages": [], "status": "active", "title": "Support Escalation"}

    conv = conversation_store[cid]
    conv["status"] = "engineer_joined"
    conv["engineerJoined"] = True
    conv["engineerJoinedAt"] = datetime.utcnow().isoformat() + "Z"
    conv["engineerName"] = engineer_name

    join_text = f"{engineer_name} has connected to this support chat session."
    if not any(m.get("kind") == "engineer_joined" or "has connected" in m.get("content", "") for m in conv.setdefault("messages", [])):
        conv["messages"].append({
            "id": f"join-{cid}-{int(time.time()*1000)}",
            "role": "system",
            "kind": "engineer_joined",
            "type": "engineer_joined",
            "engineerName": engineer_name,
            "content": join_text,
            "timestamp": conv["engineerJoinedAt"]
        })

    save_stores()

    # Broadcast to conversation clients (Maya's chat window)
    payload = {
        "type": "engineer_joined",
        "engineerName": engineer_name,
        "time": conv["engineerJoinedAt"]
    }
    await broadcast_conversation(cid, payload)

    print(f"[Chat {cid}] Support Engineer ({engineer_name}) joined.")
    return {"success": True, "status": "engineer_joined", "engineerName": engineer_name}


async def post_conversation_message(conv_id: str, sender: str, content: str) -> dict:
    """Sends a message into a conversation (used by Alex or Maya)."""
    cid = str(conv_id)
    if cid not in conversation_store:
        conversation_store[cid] = {"messages": [], "status": "active", "title": "Support Escalation"}

    conv = conversation_store[cid]
    role = "user" if sender == "user" else "engineer"
    msg = {
        "id": f"{role}-{int(time.time()*1000)}-{uuid.uuid4().hex[:4]}",
        "role": role,
        "content": content.strip(),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    conv["messages"].append(msg)
    if role == "engineer":
        conv["status"] = "engineer_joined"
        conv["engineerJoined"] = True

    save_stores()

    # Broadcast via SSE
    await broadcast_conversation(cid, {"type": "message", "message": msg})
    return {"success": True, "message": msg}

