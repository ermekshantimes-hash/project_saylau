#!/usr/bin/env python3
"""
Тест rate limiting для Public API
"""

import requests
import time
from datetime import datetime


BASE_URL = "http://127.0.0.1:8001"


def test_rate_limit():
    """
    Тест: отправить 101 запрос к /api/public/elections
    Ожидание: 101-й запрос получит 429 (Too Many Requests)
    """
    
    print("=== TEST RATE LIMIT ===")
    print(f"Endpoint: {BASE_URL}/api/public/elections")
    print("Limit: 100 requests/minute")
    print()
    
    success_count = 0
    rate_limited_count = 0
    
    # Отправить 105 запросов
    for i in range(1, 106):
        response = requests.get(f"{BASE_URL}/api/public/elections")
        
        if response.status_code == 200:
            success_count += 1
            print(f"Request {i}: ✓ 200 OK")
        elif response.status_code == 429:
            rate_limited_count += 1
            print(f"Request {i}: ✗ 429 Too Many Requests")
            print(f"  Response: {response.json()}")
        else:
            print(f"Request {i}: ? {response.status_code}")
        
        # Небольшая задержка
        time.sleep(0.1)
    
    print()
    print("=== SUMMARY ===")
    print(f"Success: {success_count}")
    print(f"Rate limited: {rate_limited_count}")
    
    if rate_limited_count > 0:
        print("✓ Rate limiting works!")
    else:
        print("✗ Rate limiting not working (all requests succeeded)")


def test_different_endpoints():
    """
    Тест: разные endpoints имеют независимые rate limits
    """
    
    print("\n=== TEST INDEPENDENT LIMITS ===")
    
    endpoints = [
        ("/api/public/elections", "100/minute"),
        ("/api/public/regions", "100/minute"),
        ("/api/public/stats/observers", "30/minute"),
        ("/api/public/stats/protocols", "30/minute"),
    ]
    
    for endpoint, limit in endpoints:
        response = requests.get(f"{BASE_URL}{endpoint}")
        print(f"{endpoint}")
        print(f"  Limit: {limit}")
        print(f"  Status: {response.status_code}")
        print()


def test_rate_limit_info():
    """
    Тест: получить информацию о rate limits
    """
    
    print("\n=== RATE LIMIT INFO ===")
    
    response = requests.get(f"{BASE_URL}/api/public/rate-limit-info")
    
    if response.status_code == 200:
        data = response.json()
        
        print("Rate limits:")
        for endpoint, limit in data["rate_limits"].items():
            print(f"  {endpoint}: {limit}")
        
        print("\nNotes:")
        for note in data["notes"]:
            print(f"  - {note}")
    else:
        print(f"Failed: {response.status_code}")


if __name__ == "__main__":
    print(f"Starting rate limit tests at {datetime.now().isoformat()}")
    print()
    
    # Test 1: Rate limit info
    test_rate_limit_info()
    
    # Test 2: Different endpoints
    test_different_endpoints()
    
    # Test 3: Rate limit enforcement (100 requests)
    # WARNING: This will send 105 requests
    confirm = input("\nSend 105 requests to test rate limiting? (yes/no): ")
    if confirm.lower() == "yes":
        test_rate_limit()
    
    print("\nTests completed.")
