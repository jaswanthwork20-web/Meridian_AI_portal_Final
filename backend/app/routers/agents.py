"""Self-help Copilot API."""
from fastapi import APIRouter
from agents import SelfHelpAgent
from knowledge_base.retriever import HybridRetriever

router = APIRouter(prefix="/api/agents", tags=["Agents"])

self_help_agent = SelfHelpAgent()
retriever = HybridRetriever.get_instance()

@router.post("/self-help/query")
def query_self_help(req: dict):
    """Answers employee inquiries using SelfHelpAgent grounded on Confluence KB."""
    query = req.get("query", "").strip()
    if not query:
        return {"error": "Query required"}

    if self_help_agent.is_greeting(query):
        reply = self_help_agent.generate_greeting_reply(query)
        return {"type": "greeting", "reply": reply, "matches": []}

    matches = retriever.search(query)
    answer = self_help_agent.generate_grounded_answer(query, matches)
    escalate, score = retriever.is_escalation_needed(matches)

    return {
        "type": "answer",
        "reply": answer or "I could not locate specific guidance in the knowledge base.",
        "matches": matches,
        "escalate": escalate,
        "top_score": score
    }

