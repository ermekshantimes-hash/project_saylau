"""
Crisis Mode Management (Task #16)
Handles read-only mode, failover, and high-load scenarios
"""

from typing import Optional
from datetime import datetime
import os
import json
from pathlib import Path

# Crisis mode state
_crisis_state = {
    "read_only": False,
    "maintenance": False,
    "reason": None,
    "activated_at": None,
    "activated_by": None,
    "cdn_fallback": False,
    "rate_limit_strict": False
}

STATE_FILE = Path("data/crisis_state.json")


def is_read_only() -> bool:
    """Check if system is in read-only mode"""
    return _crisis_state["read_only"]


def is_maintenance() -> bool:
    """Check if system is in maintenance mode"""
    return _crisis_state["maintenance"]


def is_cdn_fallback() -> bool:
    """Check if CDN fallback is active"""
    return _crisis_state["cdn_fallback"]


def enable_read_only(reason: str, activated_by: str = "system") -> dict:
    """
    Enable read-only mode (prevents writes)
    
    Args:
        reason: Reason for activation
        activated_by: User/system that activated it
        
    Returns:
        Updated state
    """
    _crisis_state["read_only"] = True
    _crisis_state["reason"] = reason
    _crisis_state["activated_at"] = datetime.utcnow().isoformat()
    _crisis_state["activated_by"] = activated_by
    
    _save_state()
    return get_state()


def disable_read_only() -> dict:
    """Disable read-only mode"""
    _crisis_state["read_only"] = False
    _crisis_state["reason"] = None
    _crisis_state["activated_at"] = None
    _crisis_state["activated_by"] = None
    
    _save_state()
    return get_state()


def enable_maintenance(reason: str, activated_by: str = "admin") -> dict:
    """Enable maintenance mode (prevents all access except admins)"""
    _crisis_state["maintenance"] = True
    _crisis_state["reason"] = reason
    _crisis_state["activated_at"] = datetime.utcnow().isoformat()
    _crisis_state["activated_by"] = activated_by
    
    _save_state()
    return get_state()


def disable_maintenance() -> dict:
    """Disable maintenance mode"""
    _crisis_state["maintenance"] = False
    _crisis_state["reason"] = None
    _crisis_state["activated_at"] = None
    _crisis_state["activated_by"] = None
    
    _save_state()
    return get_state()


def enable_cdn_fallback() -> dict:
    """Enable CDN fallback mode (serve static cached data)"""
    _crisis_state["cdn_fallback"] = True
    _save_state()
    return get_state()


def disable_cdn_fallback() -> dict:
    """Disable CDN fallback mode"""
    _crisis_state["cdn_fallback"] = False
    _save_state()
    return get_state()


def enable_strict_rate_limits() -> dict:
    """Enable stricter rate limits for high load"""
    _crisis_state["rate_limit_strict"] = True
    _save_state()
    return get_state()


def disable_strict_rate_limits() -> dict:
    """Disable strict rate limits"""
    _crisis_state["rate_limit_strict"] = False
    _save_state()
    return get_state()


def get_state() -> dict:
    """Get current crisis state"""
    return _crisis_state.copy()


def _save_state():
    """Persist crisis state to disk"""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(_crisis_state, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save crisis state: {e}")


def _load_state():
    """Load crisis state from disk"""
    global _crisis_state
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                _crisis_state.update(loaded)
    except Exception as e:
        print(f"Warning: Could not load crisis state: {e}")


# Load state on import
_load_state()


# Middleware для проверки read-only режима
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware


class ReadOnlyMiddleware(BaseHTTPMiddleware):
    """Middleware to block write operations in read-only mode"""
    
    async def dispatch(self, request: Request, call_next):
        # Check if read-only mode is active
        if is_read_only():
            # Block write operations (POST, PUT, DELETE, PATCH)
            if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
                # Allow only public API reads
                if not request.url.path.startswith("/api/public"):
                    return HTTPException(
                        status_code=503,
                        detail={
                            "error": "Service in read-only mode",
                            "reason": _crisis_state.get("reason", "System maintenance"),
                            "activated_at": _crisis_state.get("activated_at")
                        }
                    )
        
        # Check maintenance mode
        if is_maintenance():
            # Block all requests except health checks
            if not request.url.path in ["/health", "/api/crisis/status"]:
                raise HTTPException(
                    status_code=503,
                    detail={
                        "error": "Service under maintenance",
                        "reason": _crisis_state.get("reason", "Scheduled maintenance"),
                        "activated_at": _crisis_state.get("activated_at")
                    }
                )
        
        response = await call_next(request)
        return response


class MaintenanceMiddleware(BaseHTTPMiddleware):
    """Middleware to handle maintenance mode"""
    
    async def dispatch(self, request: Request, call_next):
        if is_maintenance():
            # Allow only health and status endpoints
            if request.url.path not in ["/health", "/api/crisis/status", "/docs", "/openapi.json"]:
                raise HTTPException(
                    status_code=503,
                    detail={
                        "error": "Service under maintenance",
                        "message": _crisis_state.get("reason", "System maintenance in progress"),
                        "activated_at": _crisis_state.get("activated_at"),
                        "status_check": "/api/crisis/status"
                    }
                )
        
        response = await call_next(request)
        return response
