import urllib.request
import json
import time

BASE_URL = "http://localhost:8001"

def api_post(endpoint, data, token=None):
    url = f"{BASE_URL}{endpoint}"
    body = json.dumps(data).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def api_get(endpoint, token=None):
    url = f"{BASE_URL}{endpoint}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

print("=== 1. Login as Maya Sharma ===")
login_res = api_post("/login", {"email": "maya.sharma@meridian.com", "password": "password123"})
maya_token = login_res["access_token"]
print("Logged in as Maya. Token acquired:", maya_token[:20] + "...")

print("\n=== 2. Create new Chat Session for Maya ===")
session = api_post("/sessions", {}, token=maya_token)
session_id = session["id"]
print(f"Created Session ID: {session_id}")

print("\n=== 3. Maya asks Zoom issue inquiry ===")
reply = api_post(f"/sessions/{session_id}/messages", {"message": "My Zoom audio is completely broken during all department meetings."}, token=maya_token)
print(f"Bot replied. Matches found: {len(reply.get('matches', []))}")

print("\n=== 4. Maya triggers Escalation / Route to Support (Create Jira Ticket) ===")
fb_res = api_post(f"/sessions/{session_id}/feedback", {"action": "not_resolved", "message_id": 1}, token=maya_token)
print("Escalation triggered via feedback:", fb_res)

print("\n=== 5. Support Engineer Alex Turner joins the Chat ===")
join_res = api_post(f"/api/chat/{session_id}/join", {"engineerName": "Alex Turner (Support Engineer)"})
print("Alex Turner joined:", join_res)

print("\n=== 6. Support Engineer Alex sends a message ===")
eng_msg = api_post(f"/api/chat/{session_id}/message", {
    "sender": "engineer",
    "content": "Hi Maya! Alex here from L2 IT Support. I see your audio issue on AVDGLS5-4. Connecting now."
})
print("Engineer sent message:", eng_msg)

print("\n=== 7. Maya sends follow-up live message in escalated chat ===")
user_reply = api_post(f"/sessions/{session_id}/messages", {"message": "Thank you Alex! I have the Zoom window open."}, token=maya_token)
print("User sent live reply:", user_reply)

print("\n=== 8. Verify Maya's Chat Interface (GET /sessions/{id}/messages) ===")
maya_msgs = api_get(f"/sessions/{session_id}/messages", token=maya_token)
print(f"Total messages in Maya's session: {len(maya_msgs)}")
for i, m in enumerate(maya_msgs):
    print(f"  [{i+1}] role={m.get('role')} kind={m.get('kind')} content={str(m.get('content'))[:60]}...")

kinds_in_maya = [m.get("kind") for m in maya_msgs]
roles_in_maya = [m.get("role") for m in maya_msgs]

has_jira_ticket = "jira_ticket" in kinds_in_maya
has_handoff = "handoff" in kinds_in_maya or any("Live Handoff" in (m.get("content") or "") for m in maya_msgs)
has_eng_joined = "engineer_joined" in kinds_in_maya or any("has connected" in (m.get("content") or "") for m in maya_msgs)
has_eng_message = "engineer" in roles_in_maya

print(f"  - Jira Ticket card present: {has_jira_ticket}")
print(f"  - Live Handoff broadcast present: {has_handoff}")
print(f"  - Engineer Joined broadcast present: {has_eng_joined}")
print(f"  - Engineer Message present: {has_eng_message}")

assert has_jira_ticket, "Jira ticket missing in Maya's view"
assert has_handoff, "Handoff broadcast missing in Maya's view"
assert has_eng_joined, "Engineer joined broadcast missing in Maya's view"
assert has_eng_message, "Engineer message missing in Maya's view"

print("\n=== 9. Verify Alex's Chat Console (GET /api/chat/{id}/history) ===")
alex_history = api_get(f"/api/chat/{session_id}/history")
alex_msgs = alex_history.get("messages", [])
print(f"Total messages in Alex's console: {len(alex_msgs)}")
for i, m in enumerate(alex_msgs):
    print(f"  [{i+1}] role={m.get('role')} kind={m.get('kind')} content={str(m.get('content'))[:60]}...")

alex_has_handoff = any(m.get("kind") == "handoff" or m.get("type") == "handoff" or "Live Handoff" in (m.get("content") or "") for m in alex_msgs)
alex_has_eng_joined = any(m.get("kind") == "engineer_joined" or m.get("type") == "engineer_joined" or "has connected" in (m.get("content") or "") for m in alex_msgs)
alex_has_user_msg = any(m.get("role") == "user" and "Thank you Alex" in (m.get("content") or "") for m in alex_msgs)

print(f"  - Alex view has Handoff event: {alex_has_handoff}")
print(f"  - Alex view has Engineer Joined event: {alex_has_eng_joined}")
print(f"  - Alex view has Maya's live reply: {alex_has_user_msg}")

assert alex_has_handoff, "Handoff event missing in Alex's view"
assert alex_has_eng_joined, "Engineer joined event missing in Alex's view"
assert alex_has_user_msg, "Maya's live reply missing in Alex's view"

print("\n>>> ALL ASSERTIONS PASSED! BOTH INTERFACES RECEIVE HANDOFF & JOIN EVENTS! <<<")
