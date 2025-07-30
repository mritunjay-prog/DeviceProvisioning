
import requests
import json
import random

# Config
THINGSBOARD_URL = "https://thingsboard-poc.papayaparking.com"
JWT_TOKEN = "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJzaGl2YWppLmRva2VAbmV1cmFiaXRzb2x1dGlvbi5jb20iLCJ1c2VySWQiOiJkZDFkMTAwMC02NjMzLTExZjAtOGU1YS05ZDZmYjhjYmI5OTEiLCJzY29wZXMiOlsiVEVOQU5UX0FETUlOIl0sInNlc3Npb25JZCI6IjEzMDhjM2RiLWNmYjMtNDcwOS04OWI5LTAzMjliNTM1YzRjYSIsImV4cCI6MTc1Mzc3MTc2NSwiaXNzIjoidGhpbmdzYm9hcmQuaW8iLCJpYXQiOjE3NTM3NjI3NjUsImZpcnN0TmFtZSI6IlNoaXZhamkiLCJsYXN0TmFtZSI6IkRva2UiLCJlbmFibGVkIjp0cnVlLCJpc1B1YmxpYyI6ZmFsc2UsInRlbmFudElkIjoiMGU0NDBkNTAtNGM5ZS0xMWYwLTk2MTYtMTU4M2M3ZDQyYmY1IiwiY3VzdG9tZXJJZCI6IjEzODE0MDAwLTFkZDItMTFiMi04MDgwLTgwODA4MDgwODA4MCJ9.0mntRnahm9KMJfVCDZExlW_Aset_HAcjEWxFcG2DA1QGZeYB1TApSM0FdKEBf4e6AGSBCKvDVZeF5sDcM6u0fQ"  # Truncated for readability
HEADERS = {
    "Content-Type": "application/json",
    "X-Authorization": f"Bearer {JWT_TOKEN}"
}

# Inputs
COUNTRY_NAME = "UK"
STATE_NAME = "LONDON"
DEVICE_NAME = "papaya_UK-001"
DEVICE_PROFILE_ID = "95bf2a10-6785-11f0-8e5a-9d6fb8cbb991"
SERIAL_NUMBER = "SN12345678"
LAT = 19.0760
LON = 72.8777

# Asset Profile IDs
COUNTRY_PROFILE_ID = "794f19f0-66bb-11f0-8e5a-9d6fb8cbb991"
STATE_PROFILE_ID = "93a69210-66bb-11f0-8e5a-9d6fb8cbb991"

def create_asset(name, profile_id, type_name):
    payload = {
        "name": name,
        "type": type_name,
        "assetProfileId": {
            "entityType": "ASSET_PROFILE",
            "id": profile_id
        },
        "additionalInfo": {
            "description": f"{type_name} asset created by simulator"
        }
    }
    r = requests.post(f"{THINGSBOARD_URL}/api/asset", headers=HEADERS, json=payload)
    r.raise_for_status()
    return r.json()

def send_asset_attributes(entity_type, entity_id, latitude, longitude):
    url = f"{THINGSBOARD_URL}/api/plugins/telemetry/{entity_type}/{entity_id}/attributes/SERVER_SCOPE"
    payload = {
        "latitude": latitude,
        "longitude": longitude
    }
    r = requests.post(url, headers=HEADERS, json=payload)
    r.raise_for_status()
    print(f"✅ Sent latitude/longitude to {entity_type} {entity_id}")

def create_device(name, device_profile_id):
    payload = {
        "name": name,
        "label": name,
        "deviceProfileId": {
            "entityType": "DEVICE_PROFILE",
            "id": device_profile_id
        },
        "additionalInfo": {
            "gateway": False,
            "overwriteActivityTime": False,
            "description": "Simulated IoT device"
        }
    }
    r = requests.post(f"{THINGSBOARD_URL}/api/device", headers=HEADERS, json=payload)
    r.raise_for_status()
    return r.json()

def assign_child_asset(parent_id, child_id):
    url = f"{THINGSBOARD_URL}/api/relation"
    relation_payload = {
        "from": {
            "id": parent_id,
            "entityType": "ASSET"
        },
        "to": {
            "id": child_id,
            "entityType": "ASSET"
        },
        "type": "Contains",
        "typeGroup": "COMMON"
    }
    r = requests.post(url, headers=HEADERS, json=relation_payload)
    r.raise_for_status()

def assign_device_to_asset(device_id, asset_id):
    url = f"{THINGSBOARD_URL}/api/relation"
    relation_payload = {
        "from": {
            "id": asset_id,
            "entityType": "ASSET"
        },
        "to": {
            "id": device_id,
            "entityType": "DEVICE"
        },
        "type": "Contains",
        "typeGroup": "COMMON"
    }
    r = requests.post(url, headers=HEADERS, json=relation_payload)
    r.raise_for_status()

def get_device_credentials(device_id):
    url = f"{THINGSBOARD_URL}/api/device/{device_id}/credentials"
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    return r.json()["credentialsId"]

def send_telemetry(device_token):
    telemetry_url = f"{THINGSBOARD_URL}/api/v1/{device_token}/telemetry"
    payload = {
        "serialNumber": SERIAL_NUMBER,
        "country": COUNTRY_NAME,
        "state": STATE_NAME,
        "latitude": LAT,
        "longitude": LON,
        "temperature": round(random.uniform(20, 40), 2)
    }
    r = requests.post(telemetry_url, json=payload)
    r.raise_for_status()
    print("Telemetry sent:", payload)

# ---- Execution ----

print("Creating country asset...")
country_asset = create_asset(COUNTRY_NAME, COUNTRY_PROFILE_ID, "Country")
send_asset_attributes("ASSET", country_asset["id"]["id"], 55.3781, -3.4360)  # UK lat/lon

print("Creating state asset...")
state_asset = create_asset(STATE_NAME, STATE_PROFILE_ID, "State")
send_asset_attributes("ASSET", state_asset["id"]["id"], 51.5074, -0.1278)   # London lat/lon

print("Linking state to country...")
assign_child_asset(country_asset["id"]["id"], state_asset["id"]["id"])

print("Creating device...")
device = create_device(DEVICE_NAME, DEVICE_PROFILE_ID)

print("Linking device to state...")
assign_device_to_asset(device["id"]["id"], state_asset["id"]["id"])

print("Getting device token...")
device_token = get_device_credentials(device["id"]["id"])

print("Sending telemetry...")
send_telemetry(device_token)

print("✅ All done!")
