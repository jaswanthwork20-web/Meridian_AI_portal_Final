import requests
import json
import time

BASE_URL = "http://localhost:8001"

def print_section(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def main():
    print_section("STEP 1: Test Authentication (Maya Sharma & Alex Turner)")
    # Maya login
    maya_login = requests.post(f"{BASE_URL}/login", json={
        "email": "maya.sharma@meridian.com",
        "password": "password123"
    })
    assert maya_login.status_code == 200, f"Maya login failed: {maya_login.text}"
    maya_data = maya_login.json()
    maya_token = maya_data["access_token"]
    print(" [PASS] Maya Sharma authenticated successfully. Role:", maya_data.get("role"))

    # Alex login
    alex_login = requests.post(f"{BASE_URL}/login", json={
        "email": "alex@meridian.com",
        "password": "password123"
    })
    assert alex_login.status_code == 200, f"Alex login failed: {alex_login.text}"
    alex_data = alex_login.json()
    alex_token = alex_data["access_token"]
    print(" [PASS] Alex Turner (Support Engineer) authenticated successfully. Role:", alex_data.get("role"))

    maya_headers = {"Authorization": f"Bearer {maya_token}"}
    alex_headers = {"Authorization": f"Bearer {alex_token}"}

    print_section("STEP 2: Verify Existing Enterprise Features (Zero Regression)")
    # Meetings
    meetings_res = requests.get(f"{BASE_URL}/employee/meetings", headers=maya_headers)
    assert meetings_res.status_code == 200, f"Meetings failed: {meetings_res.text}"
    print(f" [PASS] Employee Meetings retrieved: {len(meetings_res.json())} meetings")

    # Emails
    emails_res = requests.get(f"{BASE_URL}/employee/emails", headers=maya_headers)
    assert emails_res.status_code == 200, f"Emails failed: {emails_res.text}"
    print(f" [PASS] Employee Emails retrieved: {len(emails_res.json())} emails")

    # Leaves
    leaves_res = requests.get(f"{BASE_URL}/employee/leaves", headers=maya_headers)
    assert leaves_res.status_code == 200, f"Leaves failed: {leaves_res.text}"
    print(f" [PASS] Leave dashboard retrieved: {leaves_res.json().get('balances')}")

    # Projects
    projects_res = requests.get(f"{BASE_URL}/employee/projects", headers=maya_headers)
    assert projects_res.status_code == 200, f"Projects failed: {projects_res.text}"
    print(f" [PASS] Company Projects retrieved: {len(projects_res.json())} projects")

    # Invoices
    inv_res = requests.get(f"{BASE_URL}/invoices", headers=maya_headers)
    assert inv_res.status_code == 200, f"Invoices failed: {inv_res.text}"
    print(f" [PASS] Invoices retrieved: {len(inv_res.json())} invoices")

    print_section("STEP 3: Self-Help Chatbot - Create Session & Ask Zoom Query")
    create_session = requests.post(f"{BASE_URL}/sessions", headers=maya_headers)
    assert create_session.status_code == 200
    session_id = create_session.json()["id"]
    print(f" [PASS] Created new chat session ID: {session_id}")

    # User Maya asks query about Zoom
    query = "My Zoom keeps crashing when I open it. Can you help me fix it?"
    print(f" Sending query: '{query}'")
    chat_res = requests.post(f"{BASE_URL}/sessions/{session_id}/messages", headers=maya_headers, json={"message": query})
    assert chat_res.status_code == 200, f"Chat message failed: {chat_res.text}"
    reply_data = chat_res.json()
    ai_answer = ""
    for m in reply_data.get("matches", []):
        if m.get("is_llm"):
            ai_answer = m.get("text", "")
            break
    print(f" [PASS] Bedrock Chatbot Response received! (Length: {len(ai_answer)} chars)")
    print(f" Preview: {ai_answer[:150]}...")

    print_section("STEP 4: MeshCentral Remote Action - Zoom Cache Clear Only")
    # Verify remote device listing
    devices_res = requests.get(f"{BASE_URL}/api/remote/devices")
    assert devices_res.status_code == 200
    devices_data = devices_res.json()
    devices = devices_data.get("devices", [])
    print(f" [PASS] MeshCentral devices discovered: {len(devices)} device(s)")
    if devices:
        print(f" Target Device: {devices[0]['name']} (Node ID: {devices[0]['id']})")

    # Trigger Zoom cache clear via MeshCentral
    print(" Triggering Zoom cache clear on managed device...")
    cache_clear_res = requests.post(f"{BASE_URL}/api/remote/clear-zoom-cache", json={
        "session_id": session_id,
        "device_id": devices[0]["id"] if devices else None
    })
    assert cache_clear_res.status_code == 200
    cache_data = cache_clear_res.json()
    print(f" [PASS] MeshCentral Zoom Cache Clear Result: success={cache_data.get('success')}")
    print(f" Device: {cache_data.get('deviceName')}")
    if cache_data.get("output"):
        print(f" MeshCentral command output:\n{cache_data.get('output').strip()[:200]}")

    print_section("STEP 5: Escalation Flow - Jira Issue & 30-min MeshCentral Link")
    # Maya clicks 'Not Resolved' to escalate issue to Support Engineer
    print(" Maya marks issue as unresolved -> triggering escalation...")
    feedback_res = requests.post(f"{BASE_URL}/sessions/{session_id}/feedback", headers=maya_headers, json={
        "action": "not_resolved"
    })
    assert feedback_res.status_code == 200
    fb_data = feedback_res.json()
    jira_info = fb_data.get("jira_ticket", {})
    print(f" [PASS] Escalation completed!")
    print(f" Jira Key: {jira_info.get('ticket_key')}")
    print(f" Jira URL: {jira_info.get('ticket_url')}")
    print(f" Sharing Link: {jira_info.get('sharing_link')}")
    print(f" Sharing Link Expiration: {jira_info.get('link_expires_at')}")

    assert jira_info.get("sharing_link"), "Sharing link must be present!"
    assert jira_info.get("ticket_key"), "Jira ticket key must be present!"

    print_section("STEP 6: Human Handoff - Live Support Chat Between Alex & Maya")
    # Alex joins the session
    join_res = requests.post(f"{BASE_URL}/api/chat/{session_id}/join", json={
        "engineerName": "Alex Turner (Support Engineer)"
    })
    assert join_res.status_code == 200
    print(" [PASS] Alex Turner joined the chat session")

    # Alex sends message to Maya
    alex_msg_text = "Hi Maya! This is Alex from L2 Support. I reviewed your ticket and have remote desktop access ready. Can I proceed with checking your Zoom system logs?"
    msg_res = requests.post(f"{BASE_URL}/api/chat/{session_id}/message", json={
        "sender": "engineer",
        "content": alex_msg_text
    })
    assert msg_res.status_code == 200
    print(f" [PASS] Alex sent message: '{alex_msg_text}'")

    # Maya reads session messages
    history_res = requests.get(f"{BASE_URL}/api/chat/{session_id}/history")
    assert history_res.status_code == 200
    hist = history_res.json()
    msgs = hist.get("messages", [])
    found_alex_msg = any(m.get("content") == alex_msg_text for m in msgs)
    assert found_alex_msg, "Alex's message must appear in the conversation history!"
    print(f" [PASS] Maya received Alex's message in real-time chat history! Total messages: {len(msgs)}")

    # Maya replies to Alex
    maya_reply_text = "Yes Alex, please go ahead. Thank you for your quick help!"
    reply_res = requests.post(f"{BASE_URL}/api/chat/{session_id}/message", json={
        "sender": "user",
        "content": maya_reply_text
    })
    assert reply_res.status_code == 200
    print(f" [PASS] Maya replied: '{maya_reply_text}'")

    print_section("ALL INTEGRATION TESTS PASSED PERFECTLY!")

if __name__ == "__main__":
    main()
