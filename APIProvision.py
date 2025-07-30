
import requests
import json
import random
import socket
import configparser
import os
from datetime import datetime

# Load configuration from config.properties file
def load_config():
    """Load configuration from config.properties file."""
    config = configparser.ConfigParser()
    config_file = 'config.properties'
    
    if not os.path.exists(config_file):
        print(f"❌ Configuration file '{config_file}' not found!")
        exit(1)
    
    try:
        config.read(config_file)
        print(f"✅ Loaded configuration from {config_file}")
        return config
    except Exception as e:
        print(f"❌ Error reading configuration file: {e}")
        exit(1)

# Load configuration
config = load_config()

# ThingsBoard Configuration
THINGSBOARD_URL = config.get('thingsboard', 'url')
JWT_TOKEN = config.get('thingsboard', 'jwt_token')
HEADERS = {
    "Content-Type": "application/json",
    "X-Authorization": f"Bearer {JWT_TOKEN}"
}

# Asset Configuration
COUNTRY_NAME = config.get('assets', 'country_name')
STATE_NAME = config.get('assets', 'state_name')
SERIAL_NUMBER = config.get('assets', 'serial_number')


# Auto-detect laptop location and get country/state names
def get_laptop_location_and_address():
    """Get laptop's current location and address using IP-based geolocation."""
    try:
        print("🌍 Detecting laptop location...")
        
        # Using ipapi.co for free IP geolocation with detailed address info
        response = requests.get('https://ipapi.co/json/', timeout=10)
        response.raise_for_status()
        
        location_data = response.json()
        latitude = location_data.get('latitude')
        longitude = location_data.get('longitude')
        city = location_data.get('city', 'Unknown')
        region = location_data.get('region', 'Unknown')  # State/Province
        country = location_data.get('country_name', 'Unknown')
        country_code = location_data.get('country_code', 'Unknown')
        
        if latitude and longitude:
            print(f"📍 Location detected: {city}, {region}, {country}")
            print(f"📍 Coordinates: {latitude}, {longitude}")
            print(f"🏛️ Country: {country} ({country_code})")
            print(f"🏙️ State/Region: {region}")
            
            # Format names for ThingsBoard (uppercase for consistency)
            country_name = country.upper() if country != 'Unknown' else 'UNKNOWN'
            state_name = region.upper() if region != 'Unknown' else city.upper()
            
            return float(latitude), float(longitude), country_name, state_name
        else:
            print("⚠️ Could not get coordinates from IP geolocation")
            return None, None, None, None
            
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Network error getting location: {e}")
        return None, None, None, None
    except Exception as e:
        print(f"⚠️ Error getting laptop location: {e}")
        return None, None, None, None

# Get laptop's current location for coordinates only (ignore country/state from IP)
LAT, LON, _, _ = get_laptop_location_and_address()

# Always use config values for country and state names
print(f"✅ Using config values - Country: {COUNTRY_NAME}, State: {STATE_NAME}")

# Use detected coordinates if available, otherwise fallback to config coordinates
if LAT is not None and LON is not None:
    print(f"📍 Using detected coordinates: {LAT}, {LON}")
else:
    print("🔄 Falling back to config coordinates...")
    LAT = config.getfloat('location', 'latitude')
    LON = config.getfloat('location', 'longitude')
    print(f"📍 Using config coordinates: {LAT}, {LON}")

# Profile Configuration
COUNTRY_PROFILE_NAME = config.get('profiles', 'country_profile_name')
STATE_PROFILE_NAME = config.get('profiles', 'state_profile_name')
DEVICE_PROFILE_NAME = config.get('profiles', 'device_profile_name')
DEVICE_PROFILE_ID = config.get('profiles', 'device_profile_id')

# Auto-generate device name using system hostname
def generate_device_name(country, state):
    """Generate a device name based on country, state, and system hostname."""
    try:
        system_name = socket.gethostname()
        print(f"🖥️ System hostname: {system_name}")
        return f"{system_name}"
    except Exception as e:
        print(f"⚠️ Could not get system hostname: {e}")
        # Fallback to timestamp if hostname fails
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"papaya_{country}_{state}_{timestamp}"

DEVICE_NAME = generate_device_name(COUNTRY_NAME, STATE_NAME)

def validate_token():
    """Validate JWT token by checking user info."""
    try:
        url = f"{THINGSBOARD_URL}/api/auth/user"
        r = requests.get(url, headers=HEADERS)
        if r.status_code == 200:
            user_info = r.json()
            print(f"✅ Token valid - User: {user_info.get('firstName', '')} {user_info.get('lastName', '')}")
            return True
        elif r.status_code == 401:
            print("❌ Token expired or invalid")
            return False
        elif r.status_code == 403:
            print("❌ Token lacks permissions")
            return False
        else:
            print(f"❌ Token validation failed: {r.status_code}")
            return False
    except Exception as e:
        print(f"❌ Token validation error: {e}")
        return False

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
    try:
        r = requests.post(f"{THINGSBOARD_URL}/api/asset", headers=HEADERS, json=payload)
        if r.status_code == 403:
            print(f"❌ 403 Forbidden: No permission to create {type_name} assets")
            print("Check if your token has TENANT_ADMIN permissions")
            print(f"Response: {r.text}")
            raise Exception("Insufficient permissions to create assets")
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error creating {type_name}: {e}")
        print(f"Response: {r.text}")
        raise
    except Exception as e:
        print(f"❌ Error creating {type_name}: {e}")
        raise

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

def list_all_assets():
    """List all existing assets for debugging."""
    print("\n📋 All existing assets:")
    try:
        url = f"{THINGSBOARD_URL}/api/tenant/assets"
        params = {
            "pageSize": 1000,
            "page": 0,
            "sortProperty": "name",
            "sortOrder": "ASC"
        }
        r = requests.get(url, headers=HEADERS, params=params)
        r.raise_for_status()
        
        assets = r.json().get("data", [])
        if not assets:
            print("  No assets found!")
            return []
        
        for asset in assets:
            print(f"  - Name: '{asset['name']}', Type: '{asset['type']}', ID: {asset['id']['id']}")
        return assets
    except Exception as e:
        print(f"  ❌ Error fetching assets: {e}")
        return []

def find_asset_by_name(name, asset_type):
    """Find asset by name and type. Returns asset data if found, None otherwise."""
    print(f"🔍 Searching for asset: name='{name}', type='{asset_type}'")
    
    url = f"{THINGSBOARD_URL}/api/tenant/assets"
    params = {
        "pageSize": 1000,
        "page": 0,
        "sortProperty": "name",
        "sortOrder": "ASC"
    }
    r = requests.get(url, headers=HEADERS, params=params)
    r.raise_for_status()
    
    assets = r.json().get("data", [])
    print(f"📊 Found {len(assets)} total assets")
    
    # Debug: show all assets that match the name
    name_matches = [asset for asset in assets if asset["name"].lower() == name.lower()]
    if name_matches:
        print(f"🎯 Assets matching name '{name}':")
        for asset in name_matches:
            print(f"  - Name: '{asset['name']}', Type: '{asset['type']}'")
    
    # Find exact match
    for asset in assets:
        if asset["name"].lower() == name.lower() and asset["type"].lower() == asset_type.lower():
            print(f"✅ Found exact match: {asset['name']} ({asset['type']})")
            return asset
    
    print(f"❌ No exact match found for '{name}' with type '{asset_type}'")
    return None

def check_relation_exists(parent_id, child_id, parent_type="ASSET", child_type="ASSET"):
    """Check if relation already exists between two entities."""
    url = f"{THINGSBOARD_URL}/api/relation/info"
    params = {
        "fromId": parent_id,
        "fromType": parent_type,
        "toId": child_id,
        "toType": child_type,
        "relationType": "Contains"
    }
    r = requests.get(url, headers=HEADERS, params=params)
    return r.status_code == 200

def get_asset_profile_id_by_name(profile_name):
    """Get asset profile ID by name."""
    url = f"{THINGSBOARD_URL}/api/assetProfiles"
    params = {
        "pageSize": 1000,
        "page": 0,
        "textSearch": profile_name,
        "sortProperty": "name",
        "sortOrder": "ASC"
    }
    r = requests.get(url, headers=HEADERS, params=params)
    r.raise_for_status()
    
    profiles = r.json().get("data", [])
    for profile in profiles:
        if profile["name"] == profile_name:
            return profile["id"]["id"]
    return None

def get_device_profile_id_by_name(profile_name):
    """Get device profile ID by name."""
    url = f"{THINGSBOARD_URL}/api/deviceProfiles"
    params = {
        "pageSize": 1000,
        "page": 0,
        "textSearch": profile_name,
        "sortProperty": "name",
        "sortOrder": "ASC"
    }
    r = requests.get(url, headers=HEADERS, params=params)
    r.raise_for_status()
    
    profiles = r.json().get("data", [])
    for profile in profiles:
        if profile["name"] == profile_name:
            return profile["id"]["id"]
    return None

def get_all_profiles():
    """Get and display all available profiles for reference."""
    print("\n📋 Available Asset Profiles:")
    try:
        url = f"{THINGSBOARD_URL}/api/assetProfiles"
        params = {"pageSize": 100, "page": 0}
        r = requests.get(url, headers=HEADERS, params=params)
        r.raise_for_status()
        
        profiles = r.json().get("data", [])
        for profile in profiles:
            print(f"  - {profile['name']}")
    except Exception as e:
        print(f"  ❌ Error fetching asset profiles: {e}")
    
    print("\n📋 Available Device Profiles:")
    try:
        url = f"{THINGSBOARD_URL}/api/deviceProfiles"
        params = {"pageSize": 100, "page": 0}
        r = requests.get(url, headers=HEADERS, params=params)
        r.raise_for_status()
        
        profiles = r.json().get("data", [])
        for profile in profiles:
            print(f"  - {profile['name']}")
    except Exception as e:
        print(f"  ❌ Error fetching device profiles: {e}")
    print()

# ---- Execution ----

# Step 0: Validate Token First
print("Validating JWT token...")
if not validate_token():
    print("❌ Script stopped due to token validation failure")
    print("\n🔧 To fix this:")
    print("1. Get a fresh JWT token from ThingsBoard login")
    print("2. Replace the JWT_TOKEN variable with the new token")
    print("3. Ensure your user has TENANT_ADMIN permissions")
    exit(1)

print(f"🚀 Starting device provisioning for: {DEVICE_NAME}")

# Step 0.1: List all existing assets for debugging
list_all_assets()

# Step 0.5: Fetch Profile IDs dynamically
print("🔍 Fetching profile IDs...")
country_profile_id = get_asset_profile_id_by_name(COUNTRY_PROFILE_NAME)
state_profile_id = get_asset_profile_id_by_name(STATE_PROFILE_NAME)
device_profile_id = get_device_profile_id_by_name(DEVICE_PROFILE_NAME)

if not country_profile_id:
    print(f"❌ Country profile '{COUNTRY_PROFILE_NAME}' not found!")
    get_all_profiles()
    print("Please update COUNTRY_PROFILE_NAME with the correct profile name from above list")
    exit(1)

if not state_profile_id:
    print(f"❌ State profile '{STATE_PROFILE_NAME}' not found!")
    get_all_profiles()
    print("Please update STATE_PROFILE_NAME with the correct profile name from above list")
    exit(1)

if not device_profile_id:
    print(f"❌ Device profile '{DEVICE_PROFILE_NAME}' not found!")
    get_all_profiles()
    print("Please update DEVICE_PROFILE_NAME with the correct profile name from above list")
    exit(1)

print(f"✅ Found Country profile: {COUNTRY_PROFILE_NAME}")
print(f"✅ Found State profile: {STATE_PROFILE_NAME}")
print(f"✅ Found Device profile: {DEVICE_PROFILE_NAME}")

# Step 1: Handle Country Asset - Search by name regardless of type
print("Checking if country asset exists...")
country_asset = None
all_assets = list_all_assets()

# Find country asset by name (any type)
for asset in all_assets:
    if asset['name'].upper() == COUNTRY_NAME.upper():
        country_asset = asset
        print(f"✅ Found country asset: '{asset['name']}' (Type: {asset['type']})")
        break

if not country_asset:
    print(f"❌ Country asset '{COUNTRY_NAME}' not found!")
    print("🔧 Available countries in your ThingsBoard:")
    country_like_assets = [asset for asset in all_assets if any(keyword in asset['name'].upper() for keyword in ['COUNTRY', 'NATION', COUNTRY_NAME.upper()[:3]])]
    for asset in country_like_assets:
        print(f"  - {asset['name']} ({asset['type']})")
    print("\nSolutions:")
    print("1. Create the country asset manually in ThingsBoard UI")
    print("2. Or update the detected country name to match existing assets")
    exit(1)

# Step 2: Handle State Asset - Search by name regardless of type
print("Checking if state asset exists...")
state_asset = None

# Find state asset by name (any type)
for asset in all_assets:
    if asset['name'].upper() == STATE_NAME.upper():
        state_asset = asset
        print(f"✅ Found state asset: '{asset['name']}' (Type: {asset['type']})")
        break

if not state_asset:
    print(f"❌ State asset '{STATE_NAME}' not found!")
    print("🔧 Available states/regions in your ThingsBoard:")
    state_like_assets = [asset for asset in all_assets if any(keyword in asset['name'].upper() for keyword in ['STATE', 'REGION', 'PROVINCE', STATE_NAME.upper()[:3]])]
    for asset in state_like_assets:
        print(f"  - {asset['name']} ({asset['type']})")
    
    # Try to create the state asset automatically
    print(f"\n🔄 Attempting to create state asset '{STATE_NAME}' automatically...")
    try:
        # Create the state asset using the profile from config
        state_asset = create_asset(STATE_NAME, state_profile_id, STATE_PROFILE_NAME)
        print(f"✅ Successfully created state asset '{STATE_NAME}'")
        
        # Add coordinates to the new state asset (using detected location)
        send_asset_attributes("ASSET", state_asset["id"]["id"], LAT, LON)
        
    except Exception as e:
        print(f"❌ Failed to create state asset: {e}")
        print("\nManual Solutions:")
        print("1. Create the state asset manually in ThingsBoard UI")
        print("2. Or delete some unused assets to free up space")
        print("3. Or update the state name in config.properties to match existing assets")
        exit(1)

# Step 3: Link State to Country (if not already linked)
print("Checking state-country relationship...")
if not check_relation_exists(country_asset["id"]["id"], state_asset["id"]["id"]):
    print("Linking state to country...")
    assign_child_asset(country_asset["id"]["id"], state_asset["id"]["id"])
    print("✅ Linked state to country")
else:
    print("✅ State already linked to country")

# Step 4: Create Device (always create new device)
print(f"Creating device '{DEVICE_NAME}'...")
device = create_device(DEVICE_NAME, device_profile_id)
print(f"✅ Created device '{DEVICE_NAME}'")

# Step 5: Link Device to State
print("Linking device to state...")
assign_device_to_asset(device["id"]["id"], state_asset["id"]["id"])
print("✅ Linked device to state")

# Step 6: Get Device Credentials and Send Telemetry
print("Getting device token...")
device_token = get_device_credentials(device["id"]["id"])

print("Sending telemetry...")
send_telemetry(device_token)

print("✅ All done! Device provisioned successfully.")
