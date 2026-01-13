"""Test public API endpoints"""

import sys
import time

try:
    import requests
    
    base_url = "http://127.0.0.1:8002"
    
    print("Testing public API...")
    print(f"Base URL: {base_url}")
    
    # Test health endpoint
    print("\n1. Testing /api/public/health...")
    try:
        response = requests.get(f"{base_url}/api/public/health", timeout=5)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test elections list
    print("\n2. Testing /api/public/elections...")
    try:
        response = requests.get(f"{base_url}/api/public/elections", timeout=5)
        print(f"   Status: {response.status_code}")
        data = response.json()
        print(f"   Elections count: {len(data)}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test rate limit info
    print("\n3. Testing /api/public/rate-limit-info...")
    try:
        response = requests.get(f"{base_url}/api/public/rate-limit-info", timeout=5)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n✅ Tests completed")
    
except KeyboardInterrupt:
    print("\n⚠️ Interrupted by user")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ Test failed: {e}")
    sys.exit(1)
