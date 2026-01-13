# WebSocket manager for real-time updates (Task #12)

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Set
import json
import asyncio
from datetime import datetime


class ConnectionManager:
    """
    Менеджер WebSocket соединений для real-time обновлений
    """
    
    def __init__(self):
        # Активные соединения по типу подписки
        self.active_connections: Dict[str, List[WebSocket]] = {
            "protocols": [],        # Обновления протоколов
            "results": [],          # Обновления результатов
            "incidents": [],        # Обновления инцидентов
            "observers": [],        # Обновления наблюдателей
            "stats": [],           # Общая статистика
            "all": []              # Все события
        }
        
        # Соединения по УИК
        self.precinct_connections: Dict[int, List[WebSocket]] = {}
        
        # Соединения по региону
        self.region_connections: Dict[int, List[WebSocket]] = {}
        
        # Соединения пользователей (для персональных уведомлений)
        self.user_connections: Dict[int, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, channel: str = "all"):
        """
        Подключить клиента к каналу
        """
        await websocket.accept()
        
        if channel not in self.active_connections:
            self.active_connections[channel] = []
        
        self.active_connections[channel].append(websocket)
        
        # Отправить приветствие
        await self.send_personal_message(websocket, {
            "type": "connection_established",
            "channel": channel,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def disconnect(self, websocket: WebSocket, channel: str = "all"):
        """
        Отключить клиента от канала
        """
        if channel in self.active_connections:
            if websocket in self.active_connections[channel]:
                self.active_connections[channel].remove(websocket)
        
        # Удалить из precinct connections
        for precinct_id in list(self.precinct_connections.keys()):
            if websocket in self.precinct_connections[precinct_id]:
                self.precinct_connections[precinct_id].remove(websocket)
                if not self.precinct_connections[precinct_id]:
                    del self.precinct_connections[precinct_id]
        
        # Удалить из region connections
        for region_id in list(self.region_connections.keys()):
            if websocket in self.region_connections[region_id]:
                self.region_connections[region_id].remove(websocket)
                if not self.region_connections[region_id]:
                    del self.region_connections[region_id]
        
        # Удалить из user connections
        for user_id in list(self.user_connections.keys()):
            if self.user_connections[user_id] == websocket:
                del self.user_connections[user_id]
    
    async def send_personal_message(self, websocket: WebSocket, message: dict):
        """
        Отправить сообщение конкретному клиенту
        """
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"Error sending message: {e}")
    
    async def broadcast_to_channel(self, channel: str, message: dict):
        """
        Отправить сообщение всем подписчикам канала
        """
        if channel not in self.active_connections:
            return
        
        disconnected = []
        
        for connection in self.active_connections[channel]:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        
        # Удалить отключённые соединения
        for conn in disconnected:
            self.disconnect(conn, channel)
    
    async def broadcast_to_all(self, message: dict):
        """
        Отправить сообщение всем подключённым клиентам
        """
        await self.broadcast_to_channel("all", message)
    
    async def subscribe_to_precinct(self, websocket: WebSocket, precinct_id: int):
        """
        Подписать клиента на обновления УИК
        """
        if precinct_id not in self.precinct_connections:
            self.precinct_connections[precinct_id] = []
        
        if websocket not in self.precinct_connections[precinct_id]:
            self.precinct_connections[precinct_id].append(websocket)
        
        await self.send_personal_message(websocket, {
            "type": "subscribed",
            "entity": "precinct",
            "precinct_id": precinct_id
        })
    
    async def subscribe_to_region(self, websocket: WebSocket, region_id: int):
        """
        Подписать клиента на обновления региона
        """
        if region_id not in self.region_connections:
            self.region_connections[region_id] = []
        
        if websocket not in self.region_connections[region_id]:
            self.region_connections[region_id].append(websocket)
        
        await self.send_personal_message(websocket, {
            "type": "subscribed",
            "entity": "region",
            "region_id": region_id
        })
    
    async def notify_precinct(self, precinct_id: int, message: dict):
        """
        Отправить уведомление всем подписчикам УИК
        """
        if precinct_id not in self.precinct_connections:
            return
        
        disconnected = []
        
        for connection in self.precinct_connections[precinct_id]:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        
        # Удалить отключённые
        for conn in disconnected:
            if conn in self.precinct_connections[precinct_id]:
                self.precinct_connections[precinct_id].remove(conn)
    
    async def notify_region(self, region_id: int, message: dict):
        """
        Отправить уведомление всем подписчикам региона
        """
        if region_id not in self.region_connections:
            return
        
        disconnected = []
        
        for connection in self.region_connections[region_id]:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        
        # Удалить отключённые
        for conn in disconnected:
            if conn in self.region_connections[region_id]:
                self.region_connections[region_id].remove(conn)
    
    async def notify_user(self, user_id: int, message: dict):
        """
        Отправить персональное уведомление пользователю
        """
        if user_id in self.user_connections:
            try:
                await self.user_connections[user_id].send_json(message)
            except Exception:
                del self.user_connections[user_id]
    
    def register_user(self, user_id: int, websocket: WebSocket):
        """
        Зарегистрировать WebSocket соединение для пользователя
        """
        self.user_connections[user_id] = websocket
    
    def get_stats(self) -> dict:
        """
        Получить статистику подключений
        """
        return {
            "total_connections": sum(len(conns) for conns in self.active_connections.values()),
            "by_channel": {
                channel: len(conns) 
                for channel, conns in self.active_connections.items()
            },
            "precinct_subscriptions": len(self.precinct_connections),
            "region_subscriptions": len(self.region_connections),
            "user_connections": len(self.user_connections)
        }


# Глобальный менеджер соединений
manager = ConnectionManager()


# === EVENT BROADCASTING FUNCTIONS ===

async def broadcast_protocol_update(protocol_id: int, precinct_id: int, status: str, data: dict):
    """
    Отправить обновление о протоколе
    """
    message = {
        "type": "protocol_update",
        "protocol_id": protocol_id,
        "precinct_id": precinct_id,
        "status": status,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Отправить в канал protocols
    await manager.broadcast_to_channel("protocols", message)
    
    # Отправить подписчикам УИК
    await manager.notify_precinct(precinct_id, message)
    
    # Отправить в общий канал
    await manager.broadcast_to_channel("all", message)


async def broadcast_results_update(precinct_id: int, region_id: int, data: dict):
    """
    Отправить обновление результатов
    """
    message = {
        "type": "results_update",
        "precinct_id": precinct_id,
        "region_id": region_id,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Отправить в канал results
    await manager.broadcast_to_channel("results", message)
    
    # Отправить подписчикам УИК и региона
    await manager.notify_precinct(precinct_id, message)
    await manager.notify_region(region_id, message)
    
    # Отправить в общий канал
    await manager.broadcast_to_channel("all", message)


async def broadcast_incident_update(incident_id: int, precinct_id: int, severity: str, status: str, data: dict):
    """
    Отправить обновление об инциденте
    """
    message = {
        "type": "incident_update",
        "incident_id": incident_id,
        "precinct_id": precinct_id,
        "severity": severity,
        "status": status,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Отправить в канал incidents
    await manager.broadcast_to_channel("incidents", message)
    
    # Отправить подписчикам УИК
    await manager.notify_precinct(precinct_id, message)
    
    # Отправить в общий канал (только HIGH и CRITICAL)
    if severity in ["HIGH", "CRITICAL"]:
        await manager.broadcast_to_channel("all", message)


async def broadcast_observer_update(observer_id: int, status: str, data: dict):
    """
    Отправить обновление о наблюдателе
    """
    message = {
        "type": "observer_update",
        "observer_id": observer_id,
        "status": status,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Отправить в канал observers
    await manager.broadcast_to_channel("observers", message)


async def broadcast_stats_update(stats: dict):
    """
    Отправить обновление общей статистики
    """
    message = {
        "type": "stats_update",
        "stats": stats,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Отправить в канал stats
    await manager.broadcast_to_channel("stats", message)
    
    # Отправить в общий канал
    await manager.broadcast_to_channel("all", message)


async def notify_user_personal(user_id: int, notification_type: str, data: dict):
    """
    Отправить персональное уведомление пользователю
    """
    message = {
        "type": "personal_notification",
        "notification_type": notification_type,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    await manager.notify_user(user_id, message)


# === BACKGROUND TASKS ===

async def periodic_stats_broadcast():
    """
    Периодическая рассылка статистики (каждые 30 секунд)
    """
    while True:
        await asyncio.sleep(30)
        
        # Получить статистику подключений
        stats = manager.get_stats()
        
        # Отправить если есть подключения
        if stats["total_connections"] > 0:
            await broadcast_stats_update({
                "connections": stats,
                "server_time": datetime.utcnow().isoformat()
            })
