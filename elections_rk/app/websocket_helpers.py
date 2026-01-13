# WebSocket integration helpers
# Хелперы для отправки real-time уведомлений из REST endpoints

import asyncio
from app.websocket_manager import (
    broadcast_protocol_update,
    broadcast_results_update,
    broadcast_incident_update,
    broadcast_observer_update,
    broadcast_stats_update,
    notify_user_personal
)


def run_in_background(coro):
    """
    Запустить корутину в фоне (non-blocking)
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(coro)
        else:
            loop.run_until_complete(coro)
    except RuntimeError:
        # Если нет event loop, создаём новый
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(coro)


# === INTEGRATION FUNCTIONS ===

def notify_protocol_uploaded(protocol_id: int, precinct_id: int, uploader_id: int):
    """
    Уведомление о загрузке протокола
    """
    run_in_background(
        broadcast_protocol_update(
            protocol_id=protocol_id,
            precinct_id=precinct_id,
            status="uploaded",
            data={
                "uploader_id": uploader_id,
                "action": "protocol_uploaded"
            }
        )
    )


def notify_protocol_verified(protocol_id: int, precinct_id: int, verifier_id: int, status: str):
    """
    Уведомление о верификации протокола
    """
    run_in_background(
        broadcast_protocol_update(
            protocol_id=protocol_id,
            precinct_id=precinct_id,
            status=status,
            data={
                "verifier_id": verifier_id,
                "action": "protocol_verified",
                "new_status": status
            }
        )
    )


def notify_results_published(precinct_id: int, region_id: int, total_votes: int, results: dict):
    """
    Уведомление о публикации результатов
    """
    run_in_background(
        broadcast_results_update(
            precinct_id=precinct_id,
            region_id=region_id,
            data={
                "total_votes": total_votes,
                "results": results,
                "action": "results_published"
            }
        )
    )


def notify_incident_created(incident_id: int, precinct_id: int, severity: str, reporter_id: int):
    """
    Уведомление о создании инцидента
    """
    run_in_background(
        broadcast_incident_update(
            incident_id=incident_id,
            precinct_id=precinct_id,
            severity=severity,
            status="open",
            data={
                "reporter_id": reporter_id,
                "action": "incident_created"
            }
        )
    )


def notify_incident_resolved(incident_id: int, precinct_id: int, severity: str, resolver_id: int):
    """
    Уведомление о разрешении инцидента
    """
    run_in_background(
        broadcast_incident_update(
            incident_id=incident_id,
            precinct_id=precinct_id,
            severity=severity,
            status="resolved",
            data={
                "resolver_id": resolver_id,
                "action": "incident_resolved"
            }
        )
    )


def notify_observer_verified(observer_id: int, verifier_id: int, status: str):
    """
    Уведомление о верификации наблюдателя
    """
    run_in_background(
        broadcast_observer_update(
            observer_id=observer_id,
            status=status,
            data={
                "verifier_id": verifier_id,
                "action": "observer_verified",
                "new_status": status
            }
        )
    )


def notify_observer_assigned(observer_id: int, precinct_id: int, coordinator_id: int):
    """
    Уведомление о назначении наблюдателя
    """
    run_in_background(
        broadcast_observer_update(
            observer_id=observer_id,
            status="assigned",
            data={
                "precinct_id": precinct_id,
                "coordinator_id": coordinator_id,
                "action": "observer_assigned"
            }
        )
    )


def notify_user_application_status(user_id: int, application_id: int, status: str):
    """
    Персональное уведомление о статусе заявки
    """
    run_in_background(
        notify_user_personal(
            user_id=user_id,
            notification_type="application_status",
            data={
                "application_id": application_id,
                "status": status
            }
        )
    )


def notify_stats_changed(stats: dict):
    """
    Уведомление об изменении общей статистики
    """
    run_in_background(
        broadcast_stats_update(stats)
    )
