# Быстрый тест API эндпоинтов

import requests
import json

BASE_URL = "http://localhost:8001"

def test_server():
    """Проверка что сервер отвечает"""
    try:
        resp = requests.get(f"{BASE_URL}/api/elections", timeout=5)
        print(f"✓ Server responding: {resp.status_code}")
        return True
    except Exception as e:
        print(f"✗ Server not responding: {e}")
        return False

def test_audit_stats():
    """Тест статистики аудита (требует ADMIN токен)"""
    try:
        # Попытка без токена - должен дать 401
        resp = requests.get(f"{BASE_URL}/api/audit/stats")
        print(f"✓ Audit stats endpoint exists: {resp.status_code}")
        if resp.status_code == 401:
            print("  (Expected 401 - authentication required)")
        return True
    except Exception as e:
        print(f"✗ Audit stats error: {e}")
        return False

def test_verify_chain():
    """Тест верификации цепочки"""
    try:
        resp = requests.post(f"{BASE_URL}/api/audit/verify-chain")
        print(f"✓ Verify chain endpoint exists: {resp.status_code}")
        return True
    except Exception as e:
        print(f"✗ Verify chain error: {e}")
        return False

if __name__ == "__main__":
    print("=== Testing Elections RK API ===\n")
    
    if not test_server():
        print("\n✗ Server is not running. Start with: uvicorn app.main:app --reload")
        exit(1)
    
    print("\n=== Audit Endpoints ===")
    test_audit_stats()
    test_verify_chain()
    
    print("\n=== Tests Complete ===")
