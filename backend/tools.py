"""
tools.py - Centralized Tool Registry & Execution Dispatcher for Meridian Tech Helpdesk.
Consolidates all tools across RAG, MeshCentral remote remediation, Jira ticket tracking,
and L2 support escalation into a single unified interface.
"""

import os
import json
from typing import Any, Optional
from dotenv import load_dotenv

# Ensure environment is loaded
load_dotenv()

from services import meshcentral_service, jira_service, escalation_service
from knowledge_base.retriever import HybridRetriever


# ==============================================================================
# 1. TOOL DEFINITIONS
# ==============================================================================

def search_knowledge_base(query: str, top_k: int = 5) -> list[dict]:
    """
    Searches the Confluence knowledge base using hybrid dense + lexical search.
    Returns ranked document chunks with title, url, text, and relevance score.
    """
    retriever = HybridRetriever.get_instance()
    return retriever.search(query, top_k=top_k)


def list_managed_devices() -> dict:
    """Queries MeshCentral for all managed endpoints."""
    return meshcentral_service.list_managed_devices()


def get_device_info(device_id: Optional[str] = None) -> dict:
    """Retrieves detailed hardware and OS information for a specific device."""
    return meshcentral_service.get_device_info(device_id=device_id)


def clear_zoom_cache(device_id: Optional[str] = None) -> dict:
    """
    Executes remote Zoom cache clearing on the user's endpoint via MeshCentral.
    Terminates background Zoom processes, purges AppData cache directories,
    and removes temporary files.
    """
    return meshcentral_service.clear_zoom_cache(device_id=device_id)


def create_device_sharing_link(device_id: Optional[str] = None, duration_minutes: int = 30) -> dict:
    """Creates a 30-minute self-expiring remote desktop sharing link via MeshCentral."""
    return meshcentral_service.create_device_sharing_link(device_id=device_id, duration_minutes=duration_minutes)


def jira_create_ticket(
    session_id: int,
    user_email: str,
    user_query: str,
    chat_history: list[dict],
    device_info: Optional[dict] = None,
    sharing_link: Optional[str] = None
) -> dict:
    """
    Creates a Jira ticket silently in the background for dashboard tracking.
    Sets status to 'In Progress' and assignee to 'Bot'.
    """
    return jira_service.create_jira_issue(
        session_id=session_id,
        user_email=user_email,
        user_query=user_query,
        chat_history=chat_history,
        device_info=device_info,
        sharing_link=sharing_link
    )


def jira_update_ticket(ticket_key: str, status: Optional[str] = None, comment: Optional[str] = None) -> dict:
    """
    Updates a Jira ticket silently in the background (e.g. marking as 'Bot Resolved').
    """
    return jira_service.update_jira_ticket(ticket_key=ticket_key, status=status, comment=comment)


async def escalate_to_l2_support(
    session_id: int,
    user_email: str,
    issue_summary: str,
    execution_details: str,
    device_id: Optional[str] = None
) -> dict:
    """
    Escalates an unresolved issue to a human Support Engineer.
    Transitions ticket to 'L2 Confirmed', generates ephemeral remote desktop sharing link,
    and updates the Support Engineer live dashboard.
    """
    return await escalation_service.escalate_session(
        session_id=session_id,
        user_email=user_email,
        issue_summary=issue_summary,
        execution_details=execution_details,
        device_id=device_id
    )


# ==============================================================================
# 2. FRIENDLY STATUS MAPPINGS
# ==============================================================================

FRIENDLY_TOOL_STATUS: dict[str, str] = {
    "search_knowledge_base": "Searching knowledge base...",
    "jira_create_ticket": "Preparing remediation session...",
    "jira_update_ticket": "Updating diagnostic records...",
    "clear_zoom_cache": "Executing remote cache clear on device...",
    "escalate_to_l2_support": "Escalating to human Support Engineer...",
    "list_managed_devices": "Checking device connectivity...",
    "get_device_info": "Accessing device details...",
    "create_device_sharing_link": "Generating secure remote desktop link..."
}


def get_friendly_tool_status(tool_name: str) -> str:
    """Returns human-friendly processing status message for background tools."""
    return FRIENDLY_TOOL_STATUS.get(tool_name, "Processing...")


# ==============================================================================
# 3. TOOL CATALOG & METADATA REGISTRY
# ==============================================================================

TOOL_CATALOG = {
    "search_knowledge_base": {
        "name": "search_knowledge_base",
        "description": "Searches Confluence knowledge base for articles, guides, policies, and troubleshooting procedures.",
        "category": "knowledge",
        "automatable": True,
        "function": search_knowledge_base
    },
    "clear_zoom_cache": {
        "name": "clear_zoom_cache",
        "description": "Remotely clears Zoom cache and temporary files on user endpoint via MeshCentral.",
        "category": "remediation",
        "automatable": True,
        "function": clear_zoom_cache
    },
    "list_managed_devices": {
        "name": "list_managed_devices",
        "description": "Discovers online managed endpoints via MeshCentral.",
        "category": "device",
        "automatable": True,
        "function": list_managed_devices
    },
    "get_device_info": {
        "name": "get_device_info",
        "description": "Gets hardware and OS specs for a managed device.",
        "category": "device",
        "automatable": True,
        "function": get_device_info
    },
    "jira_create_ticket": {
        "name": "jira_create_ticket",
        "description": "Silently creates a background tracking ticket in Jira.",
        "category": "tracking",
        "automatable": True,
        "function": jira_create_ticket
    },
    "jira_update_ticket": {
        "name": "jira_update_ticket",
        "description": "Silently updates a Jira tracking ticket status or comments.",
        "category": "tracking",
        "automatable": True,
        "function": jira_update_ticket
    },
    "escalate_to_l2_support": {
        "name": "escalate_to_l2_support",
        "description": "Escalates session to a human L2 Support Engineer.",
        "category": "escalation",
        "automatable": True,
        "function": escalate_to_l2_support
    }
}


def execute_tool(tool_name: str, **kwargs) -> Any:
    """Executes a registered tool by name with provided keyword arguments."""
    tool_entry = TOOL_CATALOG.get(tool_name)
    if not tool_entry:
        raise ValueError(f"Unknown tool: {tool_name}")
    func = tool_entry["function"]
    return func(**kwargs)
