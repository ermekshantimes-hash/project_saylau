"""
Crisis Management API Routes (Task #16)
Administrative endpoints for managing crisis situations
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from datetime import datetime

from app.database import get_db
from app.routes_auth import get_current_user, require_role
from app.models_extended import User
from app.crisis_mode import (
    enable_read_only, disable_read_only,
    enable_maintenance, disable_maintenance,
    enable_cdn_fallback, disable_cdn_fallback,
    enable_strict_rate_limits, disable_strict_rate_limits,
    get_state, is_read_only, is_maintenance
)

router = APIRouter(prefix="/api/crisis", tags=["Crisis Management"])


# Schemas
class CrisisStateResponse(BaseModel):
    read_only: bool
    maintenance: bool
    cdn_fallback: bool
    rate_limit_strict: bool
    reason: Optional[str]
    activated_at: Optional[str]
    activated_by: Optional[str]


class EnableModeRequest(BaseModel):
    reason: str


class SystemHealthResponse(BaseModel):
    status: str
    read_only: bool
    maintenance: bool
    timestamp: str
    database_ok: bool
    api_responsive: bool


# Endpoints

@router.get("/status", response_model=CrisisStateResponse)
async def get_crisis_status():
    """
    Get current crisis mode status (Public endpoint)
    
    **No authentication required**
    """
    state = get_state()
    return CrisisStateResponse(**state)


@router.post("/read-only/enable")
async def enable_readonly_mode(
    request: EnableModeRequest,
    current_user: User = Depends(require_role(["ADMIN"]))
):
    """
    Enable read-only mode (ADMIN only)
    
    Blocks all write operations (POST/PUT/DELETE/PATCH)
    """
    state = enable_read_only(
        reason=request.reason,
        activated_by=current_user.username
    )
    
    return {
        "success": True,
        "message": "Read-only mode enabled",
        "state": state
    }


@router.post("/read-only/disable")
async def disable_readonly_mode(
    current_user: User = Depends(require_role(["ADMIN"]))
):
    """
    Disable read-only mode (ADMIN only)
    """
    state = disable_read_only()
    
    return {
        "success": True,
        "message": "Read-only mode disabled",
        "state": state
    }


@router.post("/maintenance/enable")
async def enable_maintenance_mode(
    request: EnableModeRequest,
    current_user: User = Depends(require_role(["ADMIN"]))
):
    """
    Enable maintenance mode (ADMIN only)
    
    Blocks all requests except health checks
    """
    state = enable_maintenance(
        reason=request.reason,
        activated_by=current_user.username
    )
    
    return {
        "success": True,
        "message": "Maintenance mode enabled",
        "state": state
    }


@router.post("/maintenance/disable")
async def disable_maintenance_mode(
    current_user: User = Depends(require_role(["ADMIN"]))
):
    """
    Disable maintenance mode (ADMIN only)
    """
    state = disable_maintenance()
    
    return {
        "success": True,
        "message": "Maintenance mode disabled",
        "state": state
    }


@router.post("/cdn/enable")
async def enable_cdn_mode(
    current_user: User = Depends(require_role(["ADMIN"]))
):
    """
    Enable CDN fallback mode (ADMIN only)
    
    Serves cached static data from CDN
    """
    state = enable_cdn_fallback()
    
    return {
        "success": True,
        "message": "CDN fallback enabled",
        "state": state
    }


@router.post("/cdn/disable")
async def disable_cdn_mode(
    current_user: User = Depends(require_role(["ADMIN"]))
):
    """
    Disable CDN fallback mode (ADMIN only)
    """
    state = disable_cdn_fallback()
    
    return {
        "success": True,
        "message": "CDN fallback disabled",
        "state": state
    }


@router.post("/rate-limits/strict")
async def enable_strict_limits(
    current_user: User = Depends(require_role(["ADMIN"]))
):
    """
    Enable strict rate limits (ADMIN only)
    
    Reduces rate limits by 50% for high load scenarios
    """
    state = enable_strict_rate_limits()
    
    return {
        "success": True,
        "message": "Strict rate limits enabled",
        "state": state
    }


@router.post("/rate-limits/normal")
async def disable_strict_limits(
    current_user: User = Depends(require_role(["ADMIN"]))
):
    """
    Restore normal rate limits (ADMIN only)
    """
    state = disable_strict_rate_limits()
    
    return {
        "success": True,
        "message": "Normal rate limits restored",
        "state": state
    }


@router.get("/health", response_model=SystemHealthResponse)
async def system_health_check(db: Session = Depends(get_db)):
    """
    Comprehensive system health check
    
    **No authentication required**
    """
    database_ok = True
    try:
        # Simple DB query to check connection
        db.execute("SELECT 1")
    except Exception:
        database_ok = False
    
    return SystemHealthResponse(
        status="operational" if not (is_read_only() or is_maintenance()) else "degraded",
        read_only=is_read_only(),
        maintenance=is_maintenance(),
        timestamp=datetime.utcnow().isoformat(),
        database_ok=database_ok,
        api_responsive=True
    )


@router.get("/failover-urls")
async def get_failover_urls() -> dict:
    """
    Get list of failover/mirror URLs
    
    **No authentication required**
    """
    return {
        "primary": "https://elections.gov.kz",
        "mirrors": [
            "https://elections-mirror1.gov.kz",
            "https://elections-mirror2.gov.kz",
            "https://elections-mirror3.gov.kz"
        ],
        "cdn": [
            "https://cdn1.elections.gov.kz",
            "https://cdn2.elections.gov.kz"
        ],
        "status_page": "https://status.elections.gov.kz",
        "note": "Use mirrors if primary is unavailable"
    }


@router.post("/emergency-snapshot")
async def create_emergency_snapshot(
    current_user: User = Depends(require_role(["ADMIN"])),
    db: Session = Depends(get_db)
):
    """
    Create emergency data snapshot for CDN distribution (ADMIN only)
    
    Exports critical data to static JSON for CDN caching
    """
    from sqlalchemy import func
    from app.models import Election, Region, Precinct, PrecinctResult
    
    try:
        # Get latest election
        latest_election = db.query(Election).order_by(Election.id.desc()).first()
        
        if not latest_election:
            raise HTTPException(status_code=404, detail="No elections found")
        
        # Aggregate results by region
        snapshot = {
            "generated_at": datetime.utcnow().isoformat(),
            "election": {
                "id": latest_election.id,
                "name": latest_election.name,
                "date": latest_election.election_date.isoformat() if latest_election.election_date else None
            },
            "summary": {},
            "regions": []
        }
        
        # Get total votes
        total_votes = db.query(func.sum(PrecinctResult.votes)).filter(
            PrecinctResult.election_id == latest_election.id
        ).scalar() or 0
        
        snapshot["summary"]["total_votes"] = total_votes
        snapshot["summary"]["total_precincts"] = db.query(func.count(Precinct.id)).scalar() or 0
        
        # Save snapshot
        import json
        from pathlib import Path
        
        snapshot_dir = Path("data/snapshots")
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        
        snapshot_file = snapshot_dir / f"emergency_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(snapshot_file, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False)
        
        return {
            "success": True,
            "message": "Emergency snapshot created",
            "file": str(snapshot_file),
            "size_bytes": snapshot_file.stat().st_size,
            "total_votes": total_votes
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Snapshot failed: {str(e)}")
