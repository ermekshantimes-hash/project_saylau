# WebSocket endpoints for real-time updates (Task #12)

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
import json

from app.database import get_db
from app.websocket_manager import manager
from app.models_extended import User

router = APIRouter(prefix="/ws", tags=["WebSocket"])


@router.websocket("/connect")
async def websocket_endpoint(
    websocket: WebSocket,
    channel: str = Query("all", description="protocols, results, incidents, observers, stats, all")
):
    """
    Основной WebSocket endpoint для real-time обновлений
    
    Каналы:
    - protocols: обновления протоколов
    - results: обновления результатов
    - incidents: обновления инцидентов
    - observers: обновления наблюдателей
    - stats: общая статистика
    - all: все события
    """
    await manager.connect(websocket, channel)
    
    try:
        while True:
            # Получаем сообщения от клиента
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                
                # Обработка команд от клиента
                if message.get("type") == "subscribe_precinct":
                    precinct_id = message.get("precinct_id")
                    if precinct_id:
                        await manager.subscribe_to_precinct(websocket, precinct_id)
                
                elif message.get("type") == "subscribe_region":
                    region_id = message.get("region_id")
                    if region_id:
                        await manager.subscribe_to_region(websocket, region_id)
                
                elif message.get("type") == "ping":
                    await manager.send_personal_message(websocket, {
                        "type": "pong",
                        "timestamp": message.get("timestamp")
                    })
                
            except json.JSONDecodeError:
                await manager.send_personal_message(websocket, {
                    "type": "error",
                    "message": "Invalid JSON"
                })
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel)


@router.websocket("/precinct/{precinct_id}")
async def websocket_precinct(
    websocket: WebSocket,
    precinct_id: int
):
    """
    WebSocket для обновлений конкретного УИК
    """
    await manager.connect(websocket, "all")
    await manager.subscribe_to_precinct(websocket, precinct_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                
                if message.get("type") == "ping":
                    await manager.send_personal_message(websocket, {
                        "type": "pong",
                        "precinct_id": precinct_id
                    })
            
            except json.JSONDecodeError:
                pass
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, "all")


@router.websocket("/region/{region_id}")
async def websocket_region(
    websocket: WebSocket,
    region_id: int
):
    """
    WebSocket для обновлений региона
    """
    await manager.connect(websocket, "all")
    await manager.subscribe_to_region(websocket, region_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                
                if message.get("type") == "ping":
                    await manager.send_personal_message(websocket, {
                        "type": "pong",
                        "region_id": region_id
                    })
            
            except json.JSONDecodeError:
                pass
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, "all")


@router.websocket("/user/{user_id}")
async def websocket_user(
    websocket: WebSocket,
    user_id: int
):
    """
    Персональный WebSocket для пользователя
    (для личных уведомлений)
    """
    await manager.connect(websocket, "all")
    manager.register_user(user_id, websocket)
    
    await manager.send_personal_message(websocket, {
        "type": "user_connection",
        "user_id": user_id,
        "message": "Personal notifications channel active"
    })
    
    try:
        while True:
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                
                if message.get("type") == "ping":
                    await manager.send_personal_message(websocket, {
                        "type": "pong",
                        "user_id": user_id
                    })
            
            except json.JSONDecodeError:
                pass
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, "all")
