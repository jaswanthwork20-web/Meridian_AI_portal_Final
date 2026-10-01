"""
Self-Help AI Copilot Agent (for Maya Sharma & Enterprise Employees)
Integrates AWS Bedrock (Claude 3 Haiku in ap-south-1), RAG Confluence grounding,
multi-turn conversational context, centralized tool execution, and seamless L2 human escalation.

CRITICAL DIRECTIVE: NEVER mention tickets, Jira, ticket creation, ticket updates,
ticket status, ticket IDs (e.g., KAN-6), or ticket links to the user under ANY circumstances.
All ticket operations MUST happen silently in the background.
"""

import os
import re
import json
import boto3
from pathlib import Path
from dotenv import load_dotenv

# Ensure environment is loaded
load_dotenv()

try:
    from tools import get_friendly_tool_status
except ImportError:
    def get_friendly_tool_status(tool_name: str) -> str:
        switch_map = {
            "search_knowledge_base": "Searching knowledge base...",
            "jira_create_ticket": "Preparing remediation session...",
            "jira_update_ticket": "Updating diagnostic records...",
            "clear_zoom_cache": "Executing remote cache clear on device...",
            "escalate_to_l2_support": "Escalating to human Support Engineer...",
            "list_managed_devices": "Checking device connectivity...",
            "get_device_info": "Accessing device details...",
        }
        return switch_map.get(tool_name, "Processing...")


def _load_system_prompt() -> str:
    """Load system prompt from system_prompt.py module."""
    try:
        # Import the SYSTEM_PROMPT variable from system_prompt.py
        from agents.system_prompt import SYSTEM_PROMPT
        print("[SelfHelpAgent] Successfully loaded system prompt from system_prompt.py")
        return SYSTEM_PROMPT
    except ImportError as e:
        print(f"[SelfHelpAgent] Error importing system_prompt: {e}")
        # Fallback: try to read as Python file and extract docstring
        try:
            prompt_path = Path(__file__).parent / "system_prompt.py"
            with open(prompt_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Look for SYSTEM_PROMPT variable
                match = re.search(r'SYSTEM_PROMPT\s*=\s*"""([\s\S]*?)"""', content)
                if match:
                    print("[SelfHelpAgent] Extracted system prompt from system_prompt.py file")
                    return match.group(1).strip()
        except Exception as ex:
            print(f"[SelfHelpAgent] Error reading system_prompt.py file: {ex}")
        
        # Final fallback
        print("[SelfHelpAgent] WARNING: Using minimal fallback system prompt!")
        return (
            "You are an AI-powered IT Helpdesk Assistant. "
            "Answer the employee inquiry accurately using the documentation provided. "
            "NEVER mention tickets or Jira to the user under any circumstances."
        )


BASE_SYSTEM_PROMPT = _load_system_prompt()

ACTION_DIRECTIVES = """

## Background Action Directives (Backend System Communication)
At the very end of your response on a new line, indicate if a background system action must be triggered.

**CRITICAL CONFIRMATION RULES:**
- NEVER output an action tag without EXPLICIT user confirmation FIRST
- ALWAYS ask the user for permission BEFORE outputting action tags
- ONLY output action tags AFTER the user has confirmed in their MOST RECENT message

Action tags and when to use them:
- [ACTION: clear_zoom_cache] -> Output this tag ONLY when ALL of these conditions are met:
  * The issue is SPECIFICALLY about Zoom application (freezing, crashing, performance issues)
  * You have ALREADY recommended "clear Zoom cache" or "remote Zoom fix" in a PREVIOUS message
  * The user's CURRENT message explicitly grants permission (e.g., "Yes, please execute it", "Yes, do it", "Go ahead", "Please proceed", "Yes", "Sure", "Okay, run it")
  * NEVER output this tag for camera/microphone/privacy settings issues
  * NEVER output this tag for non-Zoom issues (Teams, camera, audio, invoices, etc.)
  * NEVER output this tag when offering manual troubleshooting steps

- [ACTION: escalate_to_l2_support] -> Output this tag ONLY when:
  * You have ALREADY asked if the user wants escalation in a PREVIOUS message
  * The user's CURRENT message explicitly confirms escalation (e.g., "Yes, please escalate", "Yes, escalate", "Sure, escalate", "Yes", "Okay")
  * NEVER output this tag when first suggesting escalation

- [ACTION: resolve_issue] -> Output this tag ONLY when:
  * The user explicitly confirms their issue has been resolved (e.g., "It works now!", "Fixed, thank you!", "All good now", "Working fine")

**MULTI-TURN FLOW REQUIREMENT:**
Turn 1: Recommend action + Ask permission -> NO action tag
Turn 2: User confirms -> NOW output action tag

- CRITICAL: Do NOT perform any remote uninstallation or reinstallation actions. Software uninstallation and reinstallation are never automated remotely; provide manual self-help steps instead or offer L2 human support escalation.
- If no background system action is needed (e.g., you are asking diagnostic questions, explaining manual instructions, answering operational inquiries, greeting, or asking if they want escalation), do NOT output any [ACTION: ...] tag.
"""

TOOLS_SCHEMA = [
    {
        "name": "clear_zoom_cache",
        "description": "Clear the Zoom application cache on a remote device via MeshCentral. IMPORTANT: Only call this function AFTER the user has explicitly approved the remote action. The user will need to log in to Zoom again afterwards.",
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "The device ID or device name to clear Zoom cache on"}
            }
        }
    },
    {
        "name": "jira_update_ticket",
        "description": "Update the status of an existing Jira ticket in the background (e.g. 'Bot Resolved'). IMPORTANT: Do NOT mention ticket updates to the user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Target status: 'Bot Resolved' or 'L2 Confirmed'"},
                "comment": {"type": "string", "description": "Optional comment"}
            },
            "required": ["status"]
        }
    },
    {
        "name": "escalate_to_l2_support",
        "description": "Escalate an issue to Level 2 (L2) human support by creating a 30-minute remote desktop session. IMPORTANT: ONLY call this tool AFTER the user has explicitly confirmed they want escalation to a human Support Engineer. Never mention tickets to the user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "issue_summary": {"type": "string", "description": "Summary of issue being escalated"},
                "execution_details": {"type": "string", "description": "Details of steps attempted"}
            },
            "required": ["issue_summary"]
        }
    }
]

SYSTEM_PROMPT = BASE_SYSTEM_PROMPT + ACTION_DIRECTIVES


class SelfHelpAgent:
    def __init__(self, model_id: str = None, region_name: str = "ap-south-1"):
        load_dotenv()
        # Allow model override via environment variable
        # Options: 
        # - anthropic.claude-3-haiku-20240307-v1:0 (Fast & Cheap, but weaker)
        # - anthropic.claude-3-5-sonnet-20240620-v1:0 (Best quality, recommended)
        default_model = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
        self.model_id = model_id or default_model
        self.region_name = os.getenv("AWS_REGION", region_name)
        self._client = None
        self.system_prompt = SYSTEM_PROMPT
        
        print(f"[SelfHelpAgent] Using model: {self.model_id}")

    @property
    def client(self):
        if self._client is None:
            self._client = boto3.client(
                "bedrock-runtime",
                region_name=self.region_name
            )
        return self._client

    def is_greeting(self, query: str) -> bool:
        """
        Determines whether a message is purely a conversational greeting or chitchat.
        Never misclassifies technical issues, application names, or operational inquiries as greetings.
        """
        q = query.strip().lower()
        cleaned = re.sub(r"[^a-zA-Z0-9 ]", "", q)

        # Immediate veto: if the query contains problem words or domain topics, it is NOT a greeting
        problem_keywords = [
            "issue", "problem", "not working", "broken", "help with", "trouble", "error",
            "facing", "invoice", "zoom", "camera", "mic", "microphone", "audio", "tax",
            "gst", "sound", "headset", "stuck", "fail", "freeze", "crash", "screen",
            "unable", "cant", "permission", "device"
        ]
        if any(w in cleaned for w in problem_keywords):
            return False

        greetings = [
            "hello", "hi", "hey", "good morning", "good afternoon", "good evening",
            "who are you", "what can you do", "namaste", "greetings"
        ]
        words = cleaned.split()
        if any(cleaned == g or cleaned.startswith(g + " ") for g in greetings):
            return True
        if len(words) <= 3 and any(w in words for w in ["hi", "hello", "hey", "hiya"]):
            return True
        return False

    def generate_greeting_reply(self, user_query: str) -> str:
        """Generates a warm, professional greeting and capability overview without mentioning tickets."""
        if not self.client:
            return (
                "👋 Hello! I'm your Meridian Enterprise IT Helpdesk Assistant.\n\n"
                "I can help you with:\n"
                "• Troubleshooting work applications (Zoom, Teams, and more)\n"
                "• Audio, video, camera, and microphone issues\n"
                "• Invoice and tax code questions\n"
                "• Remote device remediation with your permission\n\n"
                "What issue are you experiencing today?"
            )
        try:
            payload = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 300,
                "temperature": 0.5,
                "system": (
                    "You are the Meridian Enterprise AI IT Helpdesk Assistant. Welcome the employee warmly and professionally. "
                    "Briefly introduce your capabilities: troubleshooting work applications (like Zoom, Microsoft Teams, and other enterprise tools), "
                    "resolving audio/video/camera/microphone issues, providing guidance on invoices and tax codes, "
                    "and executing remote device remediation actions with user permission. "
                    "Keep it concise and friendly. Ask how you can help them today. "
                    "NEVER mention tickets, Jira, or ticket tracking systems."
                ),
                "messages": [{"role": "user", "content": user_query}]
            }
            res = self.client.invoke_model(modelId=self.model_id, body=json.dumps(payload))
            body = json.loads(res["body"].read().decode("utf-8"))
            return body["content"][0]["text"].strip()
        except Exception as e:
            print(f"[SelfHelpAgent Greeting Error]: {e}")
            return (
                "👋 Hello! I'm your Meridian Enterprise IT Helpdesk Assistant.\n\n"
                "I can help you with:\n"
                "• Troubleshooting work applications (Zoom, Teams, and more)\n"
                "• Audio, video, camera, and microphone issues\n"
                "• Invoice and tax code questions\n"
                "• Remote device remediation with your permission\n\n"
                "What issue are you experiencing today?"
            )

    def generate_response(
        self,
        user_query: str,
        chat_history: list[dict] = None,
        matches: list[dict] = None
    ) -> dict:
        """
        Unified cognitive reasoning and response generator using Bedrock Claude 3 Haiku.
        Integrates:
          1. Multi-turn conversation history
          2. Grounded Confluence documentation context
          3. System prompt protocol rules (prompts.js)
          4. Background action extraction (clear_zoom_cache, escalate_to_l2_support, resolve_issue)
        """
        if not self.client:
            # Fallback if Bedrock is not configured
            return {
                "reply": "I am having trouble connecting to the AI reasoning engine. Would you like me to escalate this issue to a human Support Engineer who can assist you?",
                "action": None
            }

        try:
            # 1. Prepare Confluence Context Blocks
            # CRITICAL: Filter by relevance score to avoid confusing the LLM with irrelevant docs
            context_blocks = []
            if matches:
                # Filter matches by relevance threshold (only include score > 0.35)
                relevant_matches = [m for m in matches if m.get("score", 0) > 0.35]
                
                # If no high-score matches, take the top 1 anyway
                if not relevant_matches and matches:
                    relevant_matches = [matches[0]]
                
                print(f"[Agent Debug] Filtered {len(relevant_matches)} relevant docs from {len(matches)} total")
                for i, m in enumerate(relevant_matches[:2], 1):  # Only top 2 relevant docs
                    title = m.get("title", f"Document {i}")
                    text = m.get("text", "")
                    score = m.get("score", 0)
                    print(f"[Agent Debug] Doc {i}: {title} (score: {score:.3f})")
                    context_blocks.append(f"[{i}] {title}\n{text}")
            
            context_str = "\n\n".join(context_blocks) if context_blocks else "No specific Confluence documentation found."

            # 2. Build Multi-Turn History with Strict Alternation
            history = chat_history or []
            anthropic_messages = []

            # For Haiku, keep a tighter context window (last 6 messages = 3 turns)
            # This helps with context retention
            recent_history = history[-6:] if len(history) > 6 else history
            
            print(f"[Agent Debug] Processing {len(recent_history)} history messages (from {len(history)} total)")

            # Process history messages
            for m in recent_history:
                role = "user" if m.get("role") == "user" else "assistant"
                content = (m.get("content") or "").strip()
                if not content:
                    continue
                # Clean out internal action tags from past turns
                content = re.sub(r"\[ACTION:\s*[^\]]+\]", "", content).strip()
                content = content.replace("[ESCALATE_TO_L2]", "").replace("[CLEAR_ZOOM_CACHE]", "").strip()
                
                # Remove old KB context blocks from previous turns to save tokens
                content = re.sub(r"Verified Confluence Documentation.*?Current User Message:", "", content, flags=re.DOTALL).strip()
                if not content:
                    continue

                if anthropic_messages and anthropic_messages[-1]["role"] == role:
                    anthropic_messages[-1]["content"] += f"\n\n{content}"
                else:
                    anthropic_messages.append({"role": role, "content": content})

            # Ensure the first message is always from 'user'
            if anthropic_messages and anthropic_messages[0]["role"] == "assistant":
                anthropic_messages.pop(0)

            # 3. Enrich the LAST user message with RAG context
            # CRITICAL: Only add KB context if this is the first or second turn
            # For later turns, rely on conversation history to maintain context
            if anthropic_messages and anthropic_messages[-1]["role"] == "user":
                # Check if we should include KB context (only for early turns)
                turn_number = len([m for m in anthropic_messages if m["role"] == "user"])
                
                if turn_number <= 2 and context_str and context_str != "No specific Confluence documentation found.":
                    # Early turns: Include KB context
                    enriched_content = (
                        f"Verified Confluence Documentation (Ranked by Relevance):\n{context_str}\n\n"
                        f"CRITICAL: Use the FIRST/HIGHEST-RANKED document above as your primary reference.\n\n"
                        f"Current User Message: {anthropic_messages[-1]['content']}\n\n"
                        "Follow your system prompt step-by-step. Read previous conversation carefully."
                    )
                else:
                    # Later turns: Don't repeat KB context, focus on conversation
                    enriched_content = (
                        f"Current User Message: {anthropic_messages[-1]['content']}\n\n"
                        f"CRITICAL: This is turn {turn_number}. Review the conversation history above carefully. "
                        f"The user has already answered diagnostic questions. DO NOT repeat questions they already answered. "
                        f"Continue with the NEXT step in your troubleshooting workflow."
                    )
                
                anthropic_messages[-1]["content"] = enriched_content
            else:
                # Safety fallback: if no user message at end, append current query with context
                anthropic_messages.append({
                    "role": "user",
                    "content": (
                        f"Verified Confluence Documentation Context (Ranked by Relevance):\n{context_str}\n\n"
                        f"CRITICAL: Use the FIRST/HIGHEST-RANKED document above as your primary reference.\n\n"
                        f"User Query: {user_query}\n\n"
                        "Please respond following your system prompt guidelines and append any appropriate [ACTION: ...] tag if applicable."
                    )
                })

            # 4. Invoke Claude 3 Haiku on AWS Bedrock with native tool definitions
            payload = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,  # Increased for detailed responses
                "temperature": 0.3,  # Slightly higher to avoid repetition
                "system": self.system_prompt,
                "tools": TOOLS_SCHEMA,
                "messages": anthropic_messages
            }
            
            # Debug: Log the actual messages being sent
            print(f"[Agent Debug] Sending {len(anthropic_messages)} messages to Claude")
            print(f"[Agent Debug] System prompt length: {len(self.system_prompt)} chars")

            res = self.client.invoke_model(modelId=self.model_id, body=json.dumps(payload))
            body = json.loads(res["body"].read().decode("utf-8"))
            content_blocks = body.get("content", [])

            # Extract native tool_use calls
            tool_uses = [c for c in content_blocks if c.get("type") == "tool_use"]
            text_blocks = [c.get("text", "") for c in content_blocks if c.get("type") == "text"]
            raw_text = "\n".join(text_blocks).strip()

            action = None
            if tool_uses:
                action = tool_uses[0]["name"]

            # Fallback to action directive tags if text contains them
            if not action:
                if "[ACTION: clear_zoom_cache]" in raw_text or "[CLEAR_ZOOM_CACHE]" in raw_text:
                    action = "clear_zoom_cache"
                elif "[ACTION: escalate_to_l2_support]" in raw_text or "[ESCALATE_TO_L2]" in raw_text:
                    action = "escalate_to_l2_support"
                elif "[ACTION: resolve_issue]" in raw_text:
                    action = "resolve_issue"

            # 6. Clean text for user presentation
            clean_reply = re.sub(r"\[ACTION:\s*[^\]]+\]", "", raw_text).strip()
            clean_reply = clean_reply.replace("[ESCALATE_TO_L2]", "").replace("[CLEAR_ZOOM_CACHE]", "").strip()

            return {
                "reply": clean_reply,
                "action": action,
                "raw": raw_text
            }

        except Exception as e:
            print(f"[SelfHelpAgent Generate Error]: {e}")
            return {
                "reply": (
                    "I encountered an error processing your inquiry with our knowledge base. "
                    "Would you like me to escalate this issue to a human Support Engineer who can connect to your device remotely?"
                ),
                "action": None
            }

    # Backward-compatible wrapper
    def generate_grounded_answer(self, user_query: str, matches: list[dict]) -> str:
        res = self.generate_response(user_query=user_query, chat_history=[], matches=matches)
        return res.get("reply")

    # Contextual helpers for edge-case validation
    @staticmethod
    def _normalize_confirmation(text: str) -> str:
        """
        Normalize common abbreviations and shorthand in user confirmations.
        This ensures that casual/abbreviated user responses like 'pls go ahead'
        are correctly recognized as confirmation.
        """
        text = text.lower().strip()
        # Normalize common abbreviations
        abbreviation_map = {
            r'\bpls\b': 'please',
            r'\bplz\b': 'please',
            r'\bplease\b': 'please',
            r'\bya\b': 'yeah',
            r'\byea\b': 'yeah',
            r'\byah\b': 'yeah',
            r'\byup\b': 'yeah',
            r'\byeh\b': 'yeah',
            r'\bok\b': 'okay',
            r'\bk\b': 'okay',
            r'\bokay\b': 'okay',
            r'\balright\b': 'okay',
            r'\baight\b': 'okay',
            r'\bsure thing\b': 'sure',
            r'\bdef\b': 'definitely',
            r'\bgo for it\b': 'go ahead',
            r'\bdo it\b': 'go ahead',
            r'\blets do it\b': 'go ahead',
            r"\blet's do it\b": 'go ahead',
        }
        for pattern, replacement in abbreviation_map.items():
            text = re.sub(pattern, replacement, text)
        return text

    def _is_confirmation(self, user_query: str) -> bool:
        """
        Check if the user query is a confirmation response.
        Uses normalization + both prefix matching and substring matching
        to handle diverse confirmation styles.
        """
        q_normalized = self._normalize_confirmation(user_query)

        confirm_phrases = [
            "yes", "yeah", "yep", "sure", "okay", "ok",
            "please", "go ahead", "proceed", "do it",
            "yes please", "please do", "run it", "execute it",
            "definitely", "absolutely", "of course", "for sure",
        ]
        # Exact match or prefix match
        if any(q_normalized == w or q_normalized.startswith(w + " ") or q_normalized.startswith(w + ",") for w in confirm_phrases):
            return True
        # Substring match: handles cases like "please go ahead" or "yeah sure"
        if any(w in q_normalized for w in confirm_phrases):
            return True

        return False

    def is_escalation_confirmation(self, user_query: str, history: list = None) -> bool:
        """
        Detects if user is confirming an escalation request.
        CRITICAL: Only returns True if escalation was OFFERED in recent history AND user confirms.
        """
        q_low = user_query.lower().strip()
        
        # Check if escalation was recently offered
        escalation_was_offered = False
        if history:
            recent_texts = " ".join([
                (m.content if hasattr(m, "content") else m.get("content", "")).lower()
                for m in history[-2:]  # Only check last 2 messages
            ])
            escalation_was_offered = any(phrase in recent_texts for phrase in [
                "would you like me to escalate",
                "escalate this issue to a human",
                "escalate to a human support engineer",
                "support engineer who can connect",
                "escalate to l2",
                "connect you with a support engineer"
            ])
        
        # If escalation wasn't offered, explicit escalation phrases only
        if not escalation_was_offered:
            q_normalized = self._normalize_confirmation(user_query)
            explicit_escalation = [
                "please escalate", "yes escalate", "yes, escalate",
                "escalate to l2", "escalate to human", "connect with engineer",
                "connect me to engineer", "connect to support engineer"
            ]
            return any(phrase in q_normalized for phrase in explicit_escalation)
        
        # Escalation was offered - check for confirmation using the shared helper
        return self._is_confirmation(user_query)

    is_escalation_intent = is_escalation_confirmation

    def is_zoom_remediation_intent(self, user_query: str, history: list = None) -> bool:
        """
        Detects if user is confirming a Zoom cache clear action.
        CRITICAL: Only returns True if:
        1. The conversation is about ZOOM issues (not camera, not Teams, not other apps)
        2. Zoom cache clear was OFFERED in recent history
        3. User confirms
        """
        q_low = user_query.lower().strip()
        
        # First, verify this is a ZOOM issue conversation
        is_zoom_issue = False
        if history:
            # Check entire conversation history for Zoom context
            all_history_text = " ".join([
                (m.content if hasattr(m, "content") else m.get("content", "")).lower()
                for m in history
            ])
            # Must mention Zoom explicitly, not just camera/webcam/privacy
            is_zoom_issue = "zoom" in all_history_text
            
            # Exclude if it's about camera/webcam/privacy settings (not Zoom cache)
            privacy_keywords = ["privacy settings", "privacy permissions", "camera privacy", 
                              "privacy controls", "windows settings", "camera settings"]
            if any(keyword in all_history_text for keyword in privacy_keywords):
                # This is about manual settings, not Zoom cache clearing
                is_zoom_issue = False
        
        if not is_zoom_issue:
            # Not a Zoom issue conversation
            return False
        
        # Check if Zoom cache clear fix was recently offered
        fix_was_offered = False
        if history:
            recent_texts = " ".join([
                (m.content if hasattr(m, "content") else m.get("content", "")).lower()
                for m in history[-2:]  # Only check last 2 messages
            ])
            # Must explicitly mention Zoom cache or Zoom fix
            zoom_cache_phrases = [
                "clear zoom cache",
                "zoom cache clear",
                "clear the zoom cache",
                "remote zoom fix",
                "zoom remediation",
                "execute zoom cache"
            ]
            fix_was_offered = any(phrase in recent_texts for phrase in zoom_cache_phrases)
        
        if not fix_was_offered:
            # Only explicit Zoom cache clear requests count
            explicit_phrases = [
                "clear zoom cache", "clear the zoom cache", "clear cache",
                "clean zoom cache", "run zoom fix",
                "execute zoom cache clear", "fix zoom remotely"
            ]
            return any(phrase in q_low for phrase in explicit_phrases)
        
        # Zoom cache fix was offered - check for confirmation using the shared helper
        return self._is_confirmation(user_query)

    def is_resolved_signal(self, user_query: str, history: list = None) -> bool:
        q_low = user_query.lower().strip()
        positive_phrases = [
            "it works now", "works now", "fixed, thank you", "fixed thank you",
            "fixed now", "all good now", "all good", "working properly",
            "issue is resolved", "resolved now", "working fine now", "working fine",
            "it worked", "it is working", "it is resolved", "issue resolved",
            "problem solved", "solved now", "it solved the issue", "issue has been resolved",
            "yes it resolved", "yes it helped", "yes fixed", "yes it works", "yes it's working"
        ]
        if any(k in q_low for k in positive_phrases):
            return True
        if history:
            recent_texts = " ".join([
                (m.content if hasattr(m, "content") else m.get("content", "")).lower()
                for m in history[-2:]
            ])
            if any(p in recent_texts for p in ["did this resolve", "is the issue now resolved", "did that resolve", "resolve your issue"]):
                confirm_words = ["yes", "yeah", "yep", "fixed", "works", "thank", "resolved", "solved", "good now"]
                if any(w == q_low or q_low.startswith(w + " ") or q_low.startswith(w + ",") or f" {w} " in f" {q_low} " for w in confirm_words):
                    return True
        return False

    def is_negative_unresolved_signal(self, user_query: str, history: list = None) -> bool:
        """Only triggers if troubleshooting was recently attempted in the conversation."""
        if not history:
            return False
        recent_texts = " ".join([
            (m.content if hasattr(m, "content") else m.get("content", "")).lower()
            for m in history[-2:]
        ])
        # Only check if the bot previously gave troubleshooting instructions or asked for verification
        if not ("recommended action" in recent_texts or "did this resolve" in recent_texts or "troubleshooting" in recent_texts):
            return False

        q_low = user_query.lower().strip()
        negative_phrases = [
            "didn't resolve", "did not resolve", "didn't fix", "did not fix",
            "still freezing", "still not working", "still having the problem",
            "didn't help", "problem persists", "issue persists",
            "no, it didn't", "no that didn't", "not fixed", "no it didn't work"
        ]
        return any(k in q_low for k in negative_phrases)
