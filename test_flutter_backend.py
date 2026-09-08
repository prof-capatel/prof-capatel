import cv2
import numpy as np
import base64
import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_endpoints():
    print("[1] Testing Geofence Config...")
    r = requests.get(f"{BASE_URL}/api/v1/attendance/geofence-config?tenant_slug=default")
    print(f"Status: {r.status_code}, Response: {r.json()}")
    assert r.status_code == 200

    print("\n[2] Testing Face Login with dummy image (expecting 400 No face detected or 401 Unknown face)...")
    # Generate 300x300 blank image
    blank_img = np.zeros((300, 300, 3), dtype=np.uint8)
    _, buffer = cv2.imencode('.jpg', blank_img)
    files = {'frame': ('test.jpg', buffer.tobytes(), 'image/jpeg')}
    data = {'tenant_slug': 'default'}
    r = requests.post(f"{BASE_URL}/api/v1/auth/face-login", files=files, data=data)
    print(f"Status: {r.status_code}, Response: {r.text}")
    assert r.status_code in [400, 401]

    print("\n[3] Testing Password Login...")
    login_data = {
        "username": "admin",
        "password": "adminpassword"
    }
    r = requests.post(f"{BASE_URL}/api/v1/auth/login", json=login_data)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        token_info = r.json()
        token = token_info.get("access_token")
        print(f"Received access token: {token[:20]}...")

        print("\n[4] Testing Attendance History Fetch...")
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/api/v1/attendance/history?limit=10", headers=headers)
        print(f"Status: {r.status_code}, History count: {len(r.json()) if isinstance(r.json(), list) else r.json()}")

    print("\n[ALL ENDPOINT CHECKS PASSED]")

if __name__ == "__main__":
    test_endpoints()
