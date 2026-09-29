"""
Chat Router: Maya Copilot Sessions & Support Engineer Live Chat
Adheres strictly to prompts.js:
- NEVER mention tickets, Jira, ticket creation, ticket updates, ticket status, ticket IDs, or ticket links to the user.
- All ticket operations happen silently in the background.
- Zero button features in chatbot responses.
- Conversational escalation and diagnostic flow.
"""
import json
import uuid
import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database import get_db, ChatSession, ChatMessage, User, JiraTicket
from app.auth import get_current_user, require_employee
from services import escalation_service, meshcentral_service, jira_service
from agents import SelfHelpAgent, get_friendly_tool_status
from knowledge_base.retriever import HybridRetriever
from app.schemas import SessionOut, MessageIn, MessageOut, FeedbackIn, ChatReplyOut
import tools

router = APIRouter(tags=["Chat & Support Sessions"])

agent = SelfHelpAgent()
retriever = HybridRetriever.get_instance()

async def broadcast_tool_status(session_id: int, tool_name: str):
    """Broadcast real-time friendly tool execution status to live chat session."""
    cid = str(session_id)
    friendly_msg = get_friendly_tool_status(tool_name)
    await escalation_service.broadcast_conversation(
        cid,
        {
            "type": "status",
            "tool": tool_name,
            "message": friendly_msg
        }
    )


def make_chat_title(query: str, match_title: str | None = None) -> str:
    if match_title:
        clean = match_title.split(" - ")[0].strip()
        if len(clean) > 3:
            return clean[:45]
    clean_q = query.strip()
    words = clean_q.split()
    if len(words) <= 4:
        return clean_q.title()[:40]
    return " ".join(words[:4]).title() + "..."

@router.get("/sessions", response_model=list[SessionOut])
def get_sessions(current_user: User = Depends(require_employee), db: Session = Depends(get_db)):
    return db.query(ChatSession).filter(ChatSession.user_id == current_user.id).order_by(ChatSession.created_at.desc()).all()

@router.post("/sessions", response_model=SessionOut)
def create_session(current_user: User = Depends(require_employee), db: Session = Depends(get_db)):
    sess = ChatSession(user_id=current_user.id, title="New Conversation")
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return sess

@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
def get_session_messages(session_id: int, current_user: User = Depends(require_employee), db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    # Never return internal ticket messages to employee UI
    return [m for m in session.messages if m.kind != "jira_ticket"]

@router.post("/sessions/{session_id}/messages", response_model=ChatReplyOut)
async def post_session_message(
    session_id: int,
    req: MessageIn,
    current_user: User = Depends(require_employee),
    db: Session = Depends(get_db)
):
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    user_msg = ChatMessage(session_id=session.id, role="user", kind="text", content=req.message)
    db.add(user_msg)
    db.flush()  # Flush to make the message available in session.messages without full commit

    # Check if session is currently escalated to L2 Support Engineer
    cid = str(session.id)
    conv = escalation_service.conversation_store.get(cid)
    db_ticket = db.query(JiraTicket).filter(JiraTicket.session_id == session.id).first()
    is_live_support = (conv and conv.get("status") in ["escalated", "engineer_joined"]) or (
        db_ticket is not None and db_ticket.status in ["L2 Confirmed", "escalated", "engineer_joined"]
    ) or any(
        m.kind in ["engineer_joined"] for m in session.messages
    )

    if is_live_support:
        db.commit()
        await escalation_service.post_conversation_message(cid, "user", req.message)
        return ChatReplyOut(escalate=False, top_score=1.0, matches=[])

    # 1. Search Confluence Knowledge Base using tools.py
    await broadcast_tool_status(session.id, "search_knowledge_base")
    matches = tools.search_knowledge_base(req.message, top_k=5)
    escalate_needed, top_score = retriever.is_escalation_needed(matches)

    # 2. Update session title if New Conversation
    if session.title in ("New conversation", "New Conversation"):
        match_title = matches[0]["title"] if matches else None
        session.title = make_chat_title(req.message, match_title)

    # 3. Check for standalone greetings
    if agent.is_greeting(req.message):
        greeting_reply = agent.generate_greeting_reply(req.message)
        if session.title in ("New conversation", "New Conversation"):
            session.title = "Welcome & Greetings"
        bot_msg = ChatMessage(session_id=session.id, role="bot", kind="text", content=greeting_reply)
        db.add(bot_msg)
        db.commit()
        return ChatReplyOut(escalate=False, top_score=1.0, matches=[])

    # 4. Compile conversation history for multi-turn cognitive reasoning
    # CRITICAL: Include ALL messages up to and including the current user message
    history_contents = [
        {"role": m.role, "content": m.content}
        for m in session.messages
        if m.kind == "text" and m.content
    ]
    
    # Debug: Log history length to verify context is being maintained
    print(f"[Context Debug] Session {session.id}: {len(history_contents)} messages in history")

    # 5. Let Bedrock reason, synthesize the answer, and decide if an action is needed
    agent_result = agent.generate_response(
        user_query=req.message,
        chat_history=history_contents,
        matches=matches
    )
    action = agent_result.get("action")
    bot_reply = agent_result.get("reply", "")


    # =========================================================================
    # ACTION DISPATCHING (Executed through tools.py)
    # CRITICAL: Validate that user confirmation was given BEFORE executing actions
    # =========================================================================

    is_zoom_intent = agent.is_zoom_remediation_intent(req.message, history_contents)
    if action == "clear_zoom_cache" or (not action and is_zoom_intent):
        # Validate that the user actually confirmed in their most recent message
        if not is_zoom_intent:
            # User did not confirm - agent made a mistake, ignore the action
            # CRITICAL: Do NOT use bot_reply here - the LLM's response falsely claims
            # the action was completed. Instead, re-ask for explicit confirmation.
            print(f"[WARNING] Agent returned clear_zoom_cache action but user did not confirm. Ignoring action. User said: '{req.message}'")
            safe_reply = (
                "I'd like to help clear the Zoom cache on your device remotely. "
                "Could you please confirm — would you like me to go ahead and execute the remote Zoom cache clear on your device?"
            )
            bot_msg = ChatMessage(session_id=session.id, role="bot", kind="text", content=safe_reply)
            db.add(bot_msg)
            db.commit()
            return ChatReplyOut(
                escalate=False,
                top_score=top_score,
                matches=matches,
                tool_used="search_knowledge_base",
                tool_status=tools.get_friendly_tool_status("search_knowledge_base")
            )

        user_query = req.message
        for m in session.messages:
            if m.role == "user" and m.content and m.kind == "text":
                user_query = m.content

        # Step 1: User has confirmed to proceed with remote action.
        # CRITICAL REQUIREMENT: Self-help chatbot MUST create a Jira ticket FIRST before executing any remote action!
        await broadcast_tool_status(session.id, "jira_create_ticket")

        dev_res = tools.meshcentral_service.list_managed_devices()
        device = tools.meshcentral_service.find_device(dev_res.get("devices", [])) if dev_res.get("success") else None
        dev_name = device.get("name", "AVDGLS5-4") if device else "AVDGLS5-4"
        dev_os = device.get("os", "Microsoft Windows 11 Enterprise") if device else "Microsoft Windows 11 Enterprise"
        dev_ip = device.get("ip", "10.73.87.230") if device else "10.73.87.230"
        dev_users = device.get("currentUsers", [current_user.email]) if device else [current_user.email]
        dev_id = device.get("id") if device else None

        device_diag = {
            "name": dev_name,
            "os": dev_os,
            "ip": dev_ip,
            "currentUsers": dev_users,
            "id": dev_id
        }

        # Create Jira ticket first and register in escalation/dashboard store
        if not db_ticket:
            try:
                remed_ticket = await escalation_service.create_remediation_ticket(
                    session_id=session.id,
                    user_email=current_user.email,
                    issue_summary=f"Zoom freezing remediation - {current_user.name}",
                    device_info=device_diag,
                    execution_details="User confirmed automated remote Zoom cache clearing. Remediation initiated by Bot."
                )
                j_key = remed_ticket.get("jiraKey", f"KAN-{session.id}")
                j_url = remed_ticket.get("jiraUrl", f"https://agnishpaul2002.atlassian.net/browse/{j_key}")
                db_ticket = JiraTicket(
                    ticket_key=j_key,
                    session_id=session.id,
                    reporter_email=current_user.email,
                    summary=f"Zoom freezing remediation - {current_user.name}",
                    user_query=user_query,
                    transcript="Automated remediation initiated.",
                    status="In Progress",
                    priority="Medium",
                    ticket_url=j_url,
                    is_live=True
                )
                db.add(db_ticket)
                db.commit()
            except Exception as e:
                print(f"[RemoteAction] Jira ticket creation error: {e}")

        # Step 2: AFTER Jira ticket is created, execute the remote action
        await broadcast_tool_status(session.id, "list_managed_devices")
        await broadcast_tool_status(session.id, "get_device_info")
        await broadcast_tool_status(session.id, "clear_zoom_cache")
        res = tools.clear_zoom_cache(device_id=dev_id)
        if res.get("success"):
            dev_name = res.get("deviceName", dev_name)
            bot_text = (
                "⚡ **Remote Action Executed**\n\n"
                f"The Zoom cache clear command has been successfully executed on your managed device (**{dev_name}**).\n\n"
                "**Actions Executed:**\n"
                "• Stopped active Zoom background processes (`Zoom`, `ZoomOpener`, `CptHost`)\n"
                "• Purged corrupted application caches and CEF webcache files in `AppData\\Local\\Zoom` and `AppData\\Roaming\\Zoom`\n"
                "• Cleaned temporary lock files\n\n"
                "> 💬 **Next Steps:** Please launch Zoom again and sign in.\n\n"
                "Please test if your meetings and application are working normally. **Did this resolve your issue?**"
            )
        else:
            bot_text = (
                f"⚠️ Failed to clear Zoom cache on device: {res.get('error')}. "
                "Would you like me to escalate this issue to a human Support Engineer who can connect to your device remotely?"
            )
        bot_msg = ChatMessage(session_id=session.id, role="bot", kind="text", content=bot_text)
        db.add(bot_msg)
        db.commit()
        return ChatReplyOut(
            escalate=False,
            top_score=1.0,
            matches=[],
            tool_used="clear_zoom_cache",
            tool_status=tools.get_friendly_tool_status("clear_zoom_cache")
        )

    elif action == "escalate_to_l2_support":
        # Validate that the user actually confirmed escalation in their most recent message
        if not agent.is_escalation_confirmation(req.message, history_contents):
            # User did not confirm - agent made a mistake, ignore the action
            # CRITICAL: Do NOT use bot_reply here - the LLM's response falsely claims
            # the escalation was completed. Instead, re-ask for explicit confirmation.
            print(f"[WARNING] Agent returned escalate action but user did not confirm. Ignoring action. User said: '{req.message}'")
            safe_reply = (
                "I can escalate this issue to a human Support Engineer who can connect to your device remotely and assist you. "
                "Would you like me to go ahead with the escalation?"
            )
            bot_msg = ChatMessage(session_id=session.id, role="bot", kind="text", content=safe_reply)
            db.add(bot_msg)
            db.commit()
            return ChatReplyOut(
                escalate=False,
                top_score=top_score,
                matches=matches,
                tool_used="search_knowledge_base",
                tool_status=tools.get_friendly_tool_status("search_knowledge_base")
            )

        await broadcast_tool_status(session.id, "escalate_to_l2_support")
        user_query = req.message
        for m in session.messages:
            if m.role == "user" and m.content and m.kind == "text":
                user_query = m.content

        esc_ticket = await tools.escalate_to_l2_support(
            session_id=session.id,
            user_email=current_user.email,
            issue_summary=user_query,
            execution_details="User confirmed escalation via conversation. Routed to L2 Support Engineer."
        )

        jira_key = esc_ticket.get("jiraKey", f"KAN-{session.id}")
        jira_url = esc_ticket.get("jiraUrl", f"https://agnishpaul2002.atlassian.net/browse/{jira_key}")
        summary = esc_ticket.get("summary", f"[Support Escalation] {user_query[:75]}")

        if not db_ticket:
            db_ticket = JiraTicket(
                ticket_key=jira_key,
                session_id=session.id,
                reporter_email=current_user.email,
                summary=summary,
                user_query=user_query,
                transcript="Full conversation transcript attached to escalation.",
                status="L2 Confirmed",
                priority="High",
                ticket_url=jira_url,
                is_live=True
            )
            db.add(db_ticket)
        else:
            db_ticket.status = "L2 Confirmed"

        escalation_reply = (
            bot_reply if bot_reply and "escalat" in bot_reply.lower() else
            "I have escalated your issue to a human Support Engineer. An engineer will review your issue and connect with your device shortly to assist you."
        )
        bot_msg = ChatMessage(session_id=session.id, role="bot", kind="text", content=escalation_reply)
        db.add(bot_msg)
        db.commit()
        return ChatReplyOut(
            escalate=True,
            top_score=1.0,
            matches=[],
            tool_used="escalate_to_l2_support",
            tool_status=tools.get_friendly_tool_status("escalate_to_l2_support")
        )

    # Check if user confirms that their issue has been resolved
    is_resolved = (action == "resolve_issue") or agent.is_resolved_signal(req.message, history_contents)
    if is_resolved:
        await broadcast_tool_status(session.id, "jira_update_ticket")
        if db_ticket:
            db_ticket.status = "Bot Resolved"
            db.commit()
        try:
            target_key = db_ticket.ticket_key if db_ticket else session.id
            await escalation_service.mark_ticket_bot_resolved(
                session_id_or_key=target_key,
                comment="Automated remediation completed successfully by Bot (AI Helpdesk Assistant). User verified that the issue has been resolved."
            )
        except Exception as e:
            print(f"[ResolveIssue] Error marking ticket Bot Resolved: {e}")

        resolve_reply = (
            bot_reply if bot_reply and ("glad" in bot_reply.lower() or "resolv" in bot_reply.lower() or "fixed" in bot_reply.lower()) else
            "I'm glad to hear that resolved your issue! Please let me know if there is anything else I can help you with."
        )
        bot_msg = ChatMessage(session_id=session.id, role="bot", kind="text", content=resolve_reply)
        db.add(bot_msg)
        db.commit()
        return ChatReplyOut(
            escalate=False,
            top_score=1.0,
            matches=[],
            tool_used="jira_update_ticket",
            tool_status=tools.get_friendly_tool_status("jira_update_ticket")
        )

    # Standard grounded conversational response (Triage questions, manual self-help steps, operational guidance)
    bot_msg = ChatMessage(session_id=session.id, role="bot", kind="text", content=bot_reply)
    db.add(bot_msg)
    db.commit()
    return ChatReplyOut(
        escalate=escalate_needed,
        top_score=top_score,
        matches=matches,
        tool_used="search_knowledge_base",
        tool_status=tools.get_friendly_tool_status("search_knowledge_base")
    )

@router.post("/sessions/{session_id}/feedback")
async def record_feedback(
    session_id: int,
    feedback: FeedbackIn,
    current_user: User = Depends(require_employee),
    db: Session = Depends(get_db)
):
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if feedback.action == "not_resolved":
        user_query = "Unresolved Assistance Request"
        for m in session.messages:
            if m.role == "user" and m.content:
                user_query = m.content

        esc_ticket = await escalation_service.escalate_session(
            session_id=session.id,
            user_email=current_user.email,
            issue_summary=user_query,
            execution_details="User requested escalation. Routed to L2 Support Engineer."
        )

        jira_key = esc_ticket.get("jiraKey", f"KAN-{session.id}")
        jira_url = esc_ticket.get("jiraUrl", f"https://agnishpaul2002.atlassian.net/browse/{jira_key}")
        summary = esc_ticket.get("summary", f"[Support Escalation] {user_query[:75]}")

        db_ticket = db.query(JiraTicket).filter(JiraTicket.session_id == session.id).first()
        if not db_ticket:
            db_ticket = JiraTicket(
                ticket_key=jira_key,
                session_id=session.id,
                reporter_email=current_user.email,
                summary=summary,
                user_query=user_query,
                transcript="Full conversation transcript attached to escalation.",
                status="L2 Confirmed",
                priority="High",
                ticket_url=jira_url,
                is_live=True
            )
            db.add(db_ticket)
        else:
            db_ticket.status = "L2 Confirmed"

        bot_msg = ChatMessage(
            session_id=session.id,
            role="bot",
            kind="text",
            content="I have escalated your issue to a human Support Engineer. An engineer will review your issue and connect with your device shortly to assist you."
        )
        db.add(bot_msg)
        db.commit()
        return {
            "status": "escalated",
            "jira_ticket": {
                "ticket_key": jira_key,
                "ticket_url": jira_url,
                "sharing_link": esc_ticket.get("sharingLink"),
                "link_expires_at": esc_ticket.get("sharingLinkExpiration"),
            },
            "jiraKey": jira_key,
            "jiraUrl": jira_url,
            "sharing_link": esc_ticket.get("sharingLink"),
            "sharing_link_expiration": esc_ticket.get("sharingLinkExpiration")
        }

    if feedback.action == "resolved":
        db_ticket = db.query(JiraTicket).filter(JiraTicket.session_id == session.id).first()
        if db_ticket:
            db_ticket.status = "Bot Resolved"
            db.commit()
        try:
            target_key = db_ticket.ticket_key if db_ticket else session.id
            await escalation_service.mark_ticket_bot_resolved(
                session_id_or_key=target_key,
                comment="User marked issue as resolved via feedback rating."
            )
        except Exception as e:
            print(f"[Feedback] Error marking ticket Bot Resolved: {e}")
        return {"status": "ok", "action": "resolved"}

    return {"status": "ok", "action": "resolved"}

@router.get("/api/chat/{session_id}/history")
def get_chat_history(session_id: int, db: Session = Depends(get_db)):
    """Returns conversation history with strict single-occurrence deduplication."""
    cid = str(session_id)
    conv = escalation_service.conversation_store.get(cid, {})
    linked_ticket = next((t for t in escalation_service.escalation_store if str(t.get("conversationId")) == cid or t.get("id") == conv.get("ticketId")), None)

    db_session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    raw_messages = []
    if db_session:
        for m in db_session.messages:
            if m.kind == "jira_ticket":
                continue
            raw_messages.append({
                "id": f"msg-{m.id}",
                "role": m.role,
                "kind": getattr(m, 'kind', 'text') or 'text',
                "content": m.content,
                "timestamp": m.created_at.isoformat() if m.created_at else datetime.utcnow().isoformat()
            })

    for cm in conv.get("messages", []):
        raw_messages.append({
            "id": cm.get("id", f"conv-{uuid.uuid4().hex[:6]}"),
            "role": cm.get("role", "engineer"),
            "kind": cm.get("kind") or cm.get("type") or "text",
            "content": cm.get("content", ""),
            "timestamp": cm.get("timestamp") or datetime.utcnow().isoformat()
        })

    combined_messages = []
    seen_texts = set()
    seen_handoff = False
    seen_join = False

    for m in raw_messages:
        kind = m.get("kind") or m.get("type") or ""
        content = m.get("content") or ""
        content_str = content if isinstance(content, str) else str(content)

        is_handoff_event = (kind == "handoff") or ("Live Handoff" in content_str)
        is_join_event = (kind == "engineer_joined") or ("has connected" in content_str)

        if is_handoff_event:
            if seen_handoff:
                continue
            seen_handoff = True
            combined_messages.append(m)
            continue

        if is_join_event:
            if seen_join:
                continue
            seen_join = True
            combined_messages.append(m)
            continue

        norm_key = (m.get("role"), content_str.strip())
        if norm_key not in seen_texts:
            seen_texts.add(norm_key)
            combined_messages.append(m)

    if (conv.get("status") in ["escalated", "engineer_joined"] or linked_ticket) and not seen_handoff:
        j_key = conv.get("jiraKey") or (linked_ticket.get("jiraKey") if linked_ticket else f"KAN-{session_id}")
        combined_messages.append({
            "id": f"handoff-{cid}",
            "role": "system",
            "kind": "handoff",
            "type": "handoff",
            "content": f"⚡ Live Handoff Initiated: Issue escalated to L2 Support Engineer (Alex Turner). Jira: {j_key}.",
            "timestamp": conv.get("escalatedAt") or datetime.utcnow().isoformat()
        })

    if (conv.get("engineerJoined", False) or conv.get("status") == "engineer_joined") and not seen_join:
        eng_name = conv.get("engineerName", "Alex Turner (Support Engineer)")
        combined_messages.append({
            "id": f"join-{cid}",
            "role": "system",
            "kind": "engineer_joined",
            "type": "engineer_joined",
            "content": f"{eng_name} has connected to this support chat session.",
            "timestamp": conv.get("engineerJoinedAt") or datetime.utcnow().isoformat()
        })

    return {
        "success": True,
        "conversationId": session_id,
        "status": conv.get("status", "active"),
        "engineerJoined": conv.get("engineerJoined", False),
        "ticketId": conv.get("ticketId") or (linked_ticket.get("id") if linked_ticket else None),
        "jiraKey": conv.get("jiraKey") or (linked_ticket.get("jiraKey") if linked_ticket else None),
        "deviceName": linked_ticket.get("deviceName") if linked_ticket else "AVDGLS5-4",
        "deviceOs": linked_ticket.get("deviceOs") if linked_ticket else "Microsoft Windows 11 Enterprise",
        "issueSummary": linked_ticket.get("issueSummary") if linked_ticket else conv.get("issueSummary", "Support Escalation"),
        "sharingLink": linked_ticket.get("sharingLink") if linked_ticket else None,
        "messages": combined_messages
    }

@router.post("/api/chat/{session_id}/join")
async def chat_join(session_id: int, req: dict = None, db: Session = Depends(get_db)):
    eng_name = (req or {}).get("engineerName", "Alex Turner (Support Engineer)")
    res = await escalation_service.engineer_join_conversation(str(session_id), eng_name)
    db_sess = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if db_sess:
        join_msg = ChatMessage(
            session_id=session_id,
            role="bot",
            kind="engineer_joined",
            content=json.dumps({"engineer_name": eng_name, "message": f"{eng_name} has connected to this support chat session."})
        )
        db.add(join_msg)
        db.commit()
    return res

@router.post("/api/chat/{session_id}/message")
async def send_chat_message(session_id: int, req: dict, db: Session = Depends(get_db)):
    content = (req.get("content") or req.get("text") or "").strip()
    sender = req.get("sender", "engineer")
    if not content:
        raise HTTPException(status_code=400, detail="Content required")

    db_msg = ChatMessage(session_id=session_id, role=sender, kind="text", content=content)
    db.add(db_msg)
    db.commit()
    return await escalation_service.post_conversation_message(str(session_id), sender, content)

@router.get("/api/chat/{session_id}/live")
async def sse_chat_live(session_id: int):
    cid = str(session_id)
    q = escalation_service.subscribe_conversation(cid)
    async def event_generator():
        try:
            yield f"data: {json.dumps({'type': 'connected', 'conversationId': cid, 'time': datetime.utcnow().isoformat()})}\n\n"
            while True:
                msg = await q.get()
                yield msg
        except asyncio.CancelledError:
            pass
        finally:
            escalation_service.unsubscribe_conversation(cid, q)
    return StreamingResponse(event_generator(), media_type="text/event-stream")

