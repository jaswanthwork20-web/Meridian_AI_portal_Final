"""
Remote Management Router (strictly restricted to MeshCentral Zoom Cache Clear)
"""
from fastapi import APIRouter
from services import meshcentral_service

router = APIRouter(tags=["Remote Remediation"])

@router.get("/api/remote/devices")
def get_remote_devices():
    """Discover managed devices in MeshCentral."""
    res = meshcentral_service.list_managed_devices()
    devices = res.get("devices", []) if isinstance(res, dict) else []
    return {"success": True, "count": len(devices), "devices": devices}

@router.post("/api/remote/clear-zoom-cache")
def clear_zoom_cache(req: dict = None):
    """
    Triggers remote Zoom cache clear via MeshCentral.
    Strictly constrained to Zoom application cache purge.
    """
    req = req or {}
    dev_id = req.get("device_id") or req.get("deviceId")
    res = meshcentral_service.clear_zoom_cache(device_id=dev_id)
    return res
