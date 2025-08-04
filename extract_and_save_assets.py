import psycopg2
from psycopg2.extras import execute_values
import requests
import json
import configparser
import os
from datetime import datetime

# Database connection configuration will be loaded from config.properties
DB_CONFIG = {}

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

def load_db_config(config):
    """Load database configuration from config.properties file."""
    global DB_CONFIG
    
    try:
        DB_CONFIG = {
            "dbname": config.get('database', 'dbname', fallback='postgres'),
            "user": config.get('database', 'user', fallback='myuser'),
            "password": config.get('database', 'password', fallback='example'),
            "host": config.get('database', 'host', fallback='localhost'),
            "port": config.getint('database', 'port', fallback=5432),
            "options": config.get('database', 'options', fallback='-c search_path=papaya_parking_db')
        }
        print(f"✅ Loaded database configuration: {DB_CONFIG['user']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}")
    except Exception as e:
        print(f"❌ Error loading database configuration: {e}")
        print("Using default database configuration...")
        DB_CONFIG = {
            "dbname": "postgres",
            "user": "myuser",
            "password": "example",
            "host": "localhost",
            "port": 5432,
            "options": "-c search_path=papaya_parking_db"
        }

def connect_to_db():
    """Establish a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print("✅ Connected to the database.")
        return conn
    except Exception as e:
        print(f"❌ Failed to connect to the database: {e}")
        exit(1)

def validate_token(thingsboard_url, headers):
    """Validate JWT token by checking user info."""
    try:
        url = f"{thingsboard_url}/api/auth/user"
        r = requests.get(url, headers=headers)
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

def fetch_thingsboard_assets():
    """Fetch all assets from ThingsBoard API."""
    config = load_config()
    
    THINGSBOARD_URL = config.get('thingsboard', 'url')
    JWT_TOKEN = config.get('thingsboard', 'jwt_token')
    HEADERS = {
        "Content-Type": "application/json",
        "X-Authorization": f"Bearer {JWT_TOKEN}"
    }
    
    # Validate token first
    print("🔐 Validating JWT token...")
    if not validate_token(THINGSBOARD_URL, HEADERS):
        print("❌ Token validation failed. Please check your JWT token in config.properties")
        print("\n🔧 To fix this:")
        print("1. Login to ThingsBoard web interface")
        print("2. Open browser developer tools (F12)")
        print("3. Go to Network tab and refresh the page")
        print("4. Look for any API request and copy the 'X-Authorization' header value")
        print("5. Update the jwt_token in config.properties (remove 'Bearer ' prefix)")
        return []
    
    print("🔍 Fetching all assets from ThingsBoard...")
    try:
        url = f"{THINGSBOARD_URL}/api/tenant/assets"
        params = {
            "pageSize": 1000,
            "page": 0,
            "sortProperty": "name",
            "sortOrder": "ASC"
        }
        r = requests.get(url, headers=HEADERS, params=params)
        
        if r.status_code == 401:
            print("❌ 401 Unauthorized - Token expired or invalid")
            print("Please update your JWT token in config.properties")
            return []
        elif r.status_code == 403:
            print("❌ 403 Forbidden - Insufficient permissions")
            print("Make sure your user has TENANT_ADMIN permissions")
            return []
        
        r.raise_for_status()
        
        assets = r.json().get("data", [])
        print(f"📊 Found {len(assets)} total assets")
        return assets
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error fetching assets: {e}")
        print(f"Response: {r.text}")
        return []
    except Exception as e:
        print(f"❌ Error fetching assets: {e}")
        return []

def fetch_thingsboard_devices():
    """Fetch all devices from ThingsBoard API."""
    config = load_config()
    
    THINGSBOARD_URL = config.get('thingsboard', 'url')
    JWT_TOKEN = config.get('thingsboard', 'jwt_token')
    HEADERS = {
        "Content-Type": "application/json",
        "X-Authorization": f"Bearer {JWT_TOKEN}"
    }
    
    print("🔍 Fetching all devices from ThingsBoard...")
    try:
        url = f"{THINGSBOARD_URL}/api/tenant/devices"
        params = {
            "pageSize": 1000,
            "page": 0,
            "sortProperty": "name",
            "sortOrder": "ASC"
        }
        r = requests.get(url, headers=HEADERS, params=params)
        
        if r.status_code == 401:
            print("❌ 401 Unauthorized - Token expired or invalid")
            return []
        elif r.status_code == 403:
            print("❌ 403 Forbidden - Insufficient permissions")
            return []
        
        r.raise_for_status()
        
        devices = r.json().get("data", [])
        print(f"📊 Found {len(devices)} total devices")
        return devices
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error fetching devices: {e}")
        print(f"Response: {r.text}")
        return []
    except Exception as e:
        print(f"❌ Error fetching devices: {e}")
        return []

def categorize_assets(assets, config):
    """Categorize assets into countries and states based on profile names from config."""
    countries = []
    states = []
    devices = []
    
    # Get profile names from config
    country_profile_name = config.get('profiles', 'country_profile_name').lower()
    state_profile_name = config.get('profiles', 'state_profile_name').lower()
    device_profile_name = config.get('profiles', 'device_profile_name').lower()
    
    print(f"🔍 Looking for assets with profiles:")
    print(f"  - Country profile: {country_profile_name}")
    print(f"  - State profile: {state_profile_name}")
    print(f"  - Device profile: {device_profile_name}")
    
    for asset in assets:
        asset_type = asset.get('type', '').lower()
        asset_name = asset.get('name', '')
        
        # Categorize based on exact profile type match
        if asset_type == country_profile_name:
            countries.append(asset)
            print(f"  ✅ Found country asset: {asset_name} (Type: {asset_type})")
        elif asset_type == state_profile_name:
            states.append(asset)
            print(f"  ✅ Found state asset: {asset_name} (Type: {asset_type})")
        elif asset_type == device_profile_name:
            devices.append(asset)
            print(f"  ✅ Found device asset: {asset_name} (Type: {asset_type})")
        else:
            # Fallback categorization for assets that don't match exact profiles
            country_types = ['country', 'nation', 'territory']
            state_types = ['state', 'province', 'region', 'territory', 'district']
            
            if any(ct in asset_type for ct in country_types):
                countries.append(asset)
                print(f"  📍 Fallback country asset: {asset_name} (Type: {asset_type})")
            elif any(st in asset_type for st in state_types):
                states.append(asset)
                print(f"  📍 Fallback state asset: {asset_name} (Type: {asset_type})")
            else:
                # Check by name patterns as last resort
                if len(asset_name) <= 3 or any(keyword in asset_name.upper() for keyword in ['COUNTRY', 'NATION']):
                    countries.append(asset)
                    print(f"  🔤 Name-based country asset: {asset_name} (Type: {asset_type})")
                elif any(keyword in asset_name.upper() for keyword in ['STATE', 'PROVINCE', 'REGION']):
                    states.append(asset)
                    print(f"  🔤 Name-based state asset: {asset_name} (Type: {asset_type})")
                else:
                    devices.append(asset)
                    print(f"  ❓ Other asset (treated as device): {asset_name} (Type: {asset_type})")
    
    print(f"📋 Categorized: {len(countries)} countries, {len(states)} states, {len(devices)} other assets")
    return countries, states, devices

def save_countries_to_db(countries):
    """Save country assets to database."""
    if not countries:
        print("ℹ️ No countries to save")
        return {}
    
    conn = connect_to_db()
    country_mapping = {}
    
    try:
        with conn.cursor() as cur:
            for country in countries:
                country_name = country['name']
                
                # Insert country with conflict handling
                cur.execute("""
                    INSERT INTO country_asset (country_name, created_at)
                    VALUES (%s, %s)
                    ON CONFLICT (country_name) DO UPDATE SET
                        country_name = EXCLUDED.country_name
                    RETURNING country_id;
                """, (country_name, datetime.now()))
                
                result = cur.fetchone()
                if result:
                    country_id = result[0]
                    country_mapping[country['id']['id']] = {
                        'db_id': country_id,
                        'name': country_name
                    }
                    print(f"✅ Saved country: {country_name} (ID: {country_id})")
            
            conn.commit()
            print(f"✅ Successfully saved {len(countries)} countries")
            
    except Exception as e:
        print(f"❌ Error saving countries: {e}")
        conn.rollback()
    finally:
        conn.close()
    
    return country_mapping

def get_asset_relations(thingsboard_url, headers):
    """Fetch all asset relations from ThingsBoard to find state-country connections."""
    print("🔗 Fetching asset relations from ThingsBoard...")
    relations = {}
    
    try:
        # Get all relations - this might need pagination for large datasets
        url = f"{thingsboard_url}/api/relations"
        params = {
            "pageSize": 1000,
            "page": 0
        }
        r = requests.get(url, headers=headers, params=params)
        
        if r.status_code == 200:
            relations_data = r.json().get("data", [])
            print(f"📊 Found {len(relations_data)} total relations")
            
            for relation in relations_data:
                # Look for "Contains" relations between assets
                if (relation.get("type") == "Contains" and 
                    relation.get("from", {}).get("entityType") == "ASSET" and 
                    relation.get("to", {}).get("entityType") == "ASSET"):
                    
                    parent_id = relation["from"]["id"]
                    child_id = relation["to"]["id"]
                    relations[child_id] = parent_id
                    
            print(f"🔗 Found {len(relations)} asset parent-child relations")
        else:
            print(f"⚠️ Could not fetch relations: {r.status_code}")
            
    except Exception as e:
        print(f"⚠️ Error fetching relations: {e}")
    
    return relations

def find_state_country_mapping(states, countries, relations):
    """Find which states belong to which countries based on ThingsBoard relations."""
    state_country_map = {}
    
    print("🔍 Mapping states to countries based on relations...")
    
    # Create lookup dictionaries
    country_lookup = {country['id']['id']: country for country in countries}
    state_lookup = {state['id']['id']: state for state in states}
    
    for state in states:
        state_id = state['id']['id']
        state_name = state['name']
        
        # Check if this state has a parent relation
        if state_id in relations:
            parent_id = relations[state_id]
            
            # Check if the parent is a country
            if parent_id in country_lookup:
                country = country_lookup[parent_id]
                state_country_map[state_id] = parent_id
                print(f"  ✅ Found relation: {state_name} → {country['name']}")
            else:
                print(f"  ⚠️ State {state_name} has parent but it's not a country")
        else:
            print(f"  ❓ No parent relation found for state: {state_name}")
    
    return state_country_map

def save_states_to_db(states, country_mapping, state_country_relations):
    """Save state assets to database with proper country relationships."""
    if not states:
        print("ℹ️ No states to save")
        return {}
    
    conn = connect_to_db()
    state_mapping = {}
    
    try:
        with conn.cursor() as cur:
            for state in states:
                state_name = state['name']
                state_tb_id = state['id']['id']
                
                # Find the correct country for this state
                country_id = None
                
                if state_tb_id in state_country_relations:
                    # Get the ThingsBoard country ID
                    country_tb_id = state_country_relations[state_tb_id]
                    
                    # Find the corresponding database country ID
                    if country_tb_id in country_mapping:
                        country_id = country_mapping[country_tb_id]['db_id']
                        country_name = country_mapping[country_tb_id]['name']
                        print(f"  🔗 Mapping state '{state_name}' to country '{country_name}' (DB ID: {country_id})")
                    else:
                        print(f"  ⚠️ Country not found in mapping for state '{state_name}'")
                
                # Fallback to first available country or create default
                if country_id is None:
                    if country_mapping:
                        default_country = list(country_mapping.values())[0]
                        country_id = default_country['db_id']
                        print(f"  📍 Using default country for state '{state_name}': {default_country['name']}")
                    else:
                        # Create a default country if none exists
                        cur.execute("""
                            INSERT INTO country_asset (country_name, created_at)
                            VALUES (%s, %s)
                            ON CONFLICT (country_name) DO UPDATE SET
                                country_name = EXCLUDED.country_name
                            RETURNING country_id;
                        """, ('DEFAULT_COUNTRY', datetime.now()))
                        country_id = cur.fetchone()[0]
                        print(f"  🏗️ Created default country for state '{state_name}'")
                
                # Insert state with the correct country relationship
                cur.execute("""
                    INSERT INTO state_asset (state_name, country_id, created_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (country_id, state_name) DO UPDATE SET
                        state_name = EXCLUDED.state_name
                    RETURNING state_id;
                """, (state_name, country_id, datetime.now()))
                
                result = cur.fetchone()
                if result:
                    state_id = result[0]
                    state_mapping[state_tb_id] = {
                        'db_id': state_id,
                        'name': state_name,
                        'country_id': country_id
                    }
                    print(f"✅ Saved state: {state_name} (ID: {state_id}) → Country ID: {country_id}")
            
            conn.commit()
            print(f"✅ Successfully saved {len(states)} states with proper country relationships")
            
    except Exception as e:
        print(f"❌ Error saving states: {e}")
        conn.rollback()
    finally:
        conn.close()
    
    return state_mapping

def get_asset_attributes(asset_id, thingsboard_url, headers):
    """Fetch asset attributes (like coordinates) from ThingsBoard."""
    try:
        url = f"{thingsboard_url}/api/plugins/telemetry/ASSET/{asset_id}/values/attributes/SERVER_SCOPE"
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            attributes = r.json()
            lat = None
            lon = None
            
            for attr in attributes:
                if attr['key'] == 'latitude':
                    lat = float(attr['value'])
                elif attr['key'] == 'longitude':
                    lon = float(attr['value'])
            
            return lat, lon
        return None, None
    except Exception as e:
        print(f"⚠️ Could not fetch attributes for asset {asset_id}: {e}")
        return None, None

def get_device_attributes(device_id, thingsboard_url, headers):
    """Fetch device attributes (like coordinates, firmware version) from ThingsBoard."""
    try:
        # Get server-side attributes
        url = f"{thingsboard_url}/api/plugins/telemetry/DEVICE/{device_id}/values/attributes/SERVER_SCOPE"
        r = requests.get(url, headers=headers)
        
        lat = None
        lon = None
        firmware_version = "1.0.0"  # Default
        
        if r.status_code == 200:
            attributes = r.json()
            for attr in attributes:
                if attr['key'] == 'latitude':
                    lat = float(attr['value'])
                elif attr['key'] == 'longitude':
                    lon = float(attr['value'])
                elif attr['key'] in ['firmwareVersion', 'firmware_version', 'version']:
                    firmware_version = str(attr['value'])
        
        # Also try client-side attributes
        url_client = f"{thingsboard_url}/api/plugins/telemetry/DEVICE/{device_id}/values/attributes/CLIENT_SCOPE"
        r_client = requests.get(url_client, headers=headers)
        
        if r_client.status_code == 200:
            client_attributes = r_client.json()
            for attr in client_attributes:
                if attr['key'] == 'latitude' and lat is None:
                    lat = float(attr['value'])
                elif attr['key'] == 'longitude' and lon is None:
                    lon = float(attr['value'])
                elif attr['key'] in ['firmwareVersion', 'firmware_version', 'version']:
                    firmware_version = str(attr['value'])
        
        return lat, lon, firmware_version
    except Exception as e:
        print(f"⚠️ Could not fetch attributes for device {device_id}: {e}")
        return None, None, "1.0.0"

def save_asset_devices_to_db(devices, state_mapping, country_mapping):
    """Save device-like assets to database as devices."""
    if not devices:
        print("ℹ️ No asset devices to save")
        return
    
    config = load_config()
    THINGSBOARD_URL = config.get('thingsboard', 'url')
    JWT_TOKEN = config.get('thingsboard', 'jwt_token')
    HEADERS = {
        "Content-Type": "application/json",
        "X-Authorization": f"Bearer {JWT_TOKEN}"
    }
    
    conn = connect_to_db()
    
    try:
        with conn.cursor() as cur:
            for device in devices:
                device_name = device['name']
                
                # Generate a serial number if not available
                serial_number = f"ASSET_{device['id']['id'][:8]}"
                firmware_version = "1.0.0"  # Default version
                
                # Try to get coordinates from ThingsBoard
                lat, lon = get_asset_attributes(device['id']['id'], THINGSBOARD_URL, HEADERS)
                
                # Use default coordinates if not found
                if lat is None or lon is None:
                    lat, lon = 0.0, 0.0
                
                # Assign to first available state/country
                if state_mapping:
                    default_state = list(state_mapping.values())[0]
                    state_id = default_state['db_id']
                    country_id = default_state['country_id']
                elif country_mapping:
                    default_country = list(country_mapping.values())[0]
                    country_id = default_country['db_id']
                    # Create a default state
                    cur.execute("""
                        INSERT INTO state_asset (state_name, country_id, created_at)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (country_id, state_name) DO UPDATE SET
                            state_name = EXCLUDED.state_name
                        RETURNING state_id;
                    """, ('DEFAULT_STATE', country_id, datetime.now()))
                    state_id = cur.fetchone()[0]
                else:
                    # Create default country and state
                    cur.execute("""
                        INSERT INTO country_asset (country_name, created_at)
                        VALUES (%s, %s)
                        ON CONFLICT (country_name) DO UPDATE SET
                            country_name = EXCLUDED.country_name
                        RETURNING country_id;
                    """, ('DEFAULT_COUNTRY', datetime.now()))
                    country_id = cur.fetchone()[0]
                    
                    cur.execute("""
                        INSERT INTO state_asset (state_name, country_id, created_at)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (country_id, state_name) DO UPDATE SET
                            state_name = EXCLUDED.state_name
                        RETURNING state_id;
                    """, ('DEFAULT_STATE', country_id, datetime.now()))
                    state_id = cur.fetchone()[0]
                
                # Insert device
                cur.execute("""
                    INSERT INTO devices (device_name, serial_number, firmware_version, 
                                       location_lat, location_lon, state_id, country_id, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (serial_number) DO UPDATE SET
                        device_name = EXCLUDED.device_name,
                        firmware_version = EXCLUDED.firmware_version,
                        location_lat = EXCLUDED.location_lat,
                        location_lon = EXCLUDED.location_lon
                    RETURNING device_id;
                """, (device_name, serial_number, firmware_version, lat, lon, 
                      state_id, country_id, datetime.now()))
                
                result = cur.fetchone()
                if result:
                    print(f"✅ Saved asset device: {device_name} (Serial: {serial_number})")
            
            conn.commit()
            print(f"✅ Successfully saved {len(devices)} asset devices")
            
    except Exception as e:
        print(f"❌ Error saving asset devices: {e}")
        conn.rollback()
    finally:
        conn.close()

def save_thingsboard_devices_to_db(tb_devices, state_mapping, country_mapping):
    """Save actual ThingsBoard devices to database."""
    if not tb_devices:
        print("ℹ️ No ThingsBoard devices to save")
        return
    
    config = load_config()
    THINGSBOARD_URL = config.get('thingsboard', 'url')
    JWT_TOKEN = config.get('thingsboard', 'jwt_token')
    HEADERS = {
        "Content-Type": "application/json",
        "X-Authorization": f"Bearer {JWT_TOKEN}"
    }
    
    conn = connect_to_db()
    
    try:
        with conn.cursor() as cur:
            for device in tb_devices:
                device_name = device['name']
                device_id = device['id']['id']
                
                # Use device label as serial number if available, otherwise generate one
                serial_number = device.get('label', f"DEV_{device_id[:8]}")
                if not serial_number:
                    serial_number = f"DEV_{device_id[:8]}"
                
                # Get device attributes (coordinates, firmware version)
                lat, lon, firmware_version = get_device_attributes(device_id, THINGSBOARD_URL, HEADERS)
                
                # Use default coordinates if not found
                if lat is None or lon is None:
                    lat, lon = 0.0, 0.0
                
                # Assign to first available state/country
                if state_mapping:
                    default_state = list(state_mapping.values())[0]
                    state_id = default_state['db_id']
                    country_id = default_state['country_id']
                elif country_mapping:
                    default_country = list(country_mapping.values())[0]
                    country_id = default_country['db_id']
                    # Create a default state
                    cur.execute("""
                        INSERT INTO state_asset (state_name, country_id, created_at)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (country_id, state_name) DO UPDATE SET
                            state_name = EXCLUDED.state_name
                        RETURNING state_id;
                    """, ('DEFAULT_STATE', country_id, datetime.now()))
                    state_id = cur.fetchone()[0]
                else:
                    # Create default country and state
                    cur.execute("""
                        INSERT INTO country_asset (country_name, created_at)
                        VALUES (%s, %s)
                        ON CONFLICT (country_name) DO UPDATE SET
                            country_name = EXCLUDED.country_name
                        RETURNING country_id;
                    """, ('DEFAULT_COUNTRY', datetime.now()))
                    country_id = cur.fetchone()[0]
                    
                    cur.execute("""
                        INSERT INTO state_asset (state_name, country_id, created_at)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (country_id, state_name) DO UPDATE SET
                            state_name = EXCLUDED.state_name
                        RETURNING state_id;
                    """, ('DEFAULT_STATE', country_id, datetime.now()))
                    state_id = cur.fetchone()[0]
                
                # Insert device
                cur.execute("""
                    INSERT INTO devices (device_name, serial_number, firmware_version, 
                                       location_lat, location_lon, state_id, country_id, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (serial_number) DO UPDATE SET
                        device_name = EXCLUDED.device_name,
                        firmware_version = EXCLUDED.firmware_version,
                        location_lat = EXCLUDED.location_lat,
                        location_lon = EXCLUDED.location_lon
                    RETURNING device_id;
                """, (device_name, serial_number, firmware_version, lat, lon, 
                      state_id, country_id, datetime.now()))
                
                result = cur.fetchone()
                if result:
                    print(f"✅ Saved ThingsBoard device: {device_name} (Serial: {serial_number})")
            
            conn.commit()
            print(f"✅ Successfully saved {len(tb_devices)} ThingsBoard devices")
            
    except Exception as e:
        print(f"❌ Error saving ThingsBoard devices: {e}")
        conn.rollback()
    finally:
        conn.close()

def main():
    """Main execution function."""
    print("🚀 Starting ThingsBoard asset and device extraction and database save...")
    
    # Load config for categorization and database
    config = load_config()
    load_db_config(config)
    
    # Fetch all assets from ThingsBoard
    assets = fetch_thingsboard_assets()
    if not assets:
        print("❌ No assets found. Exiting.")
        return
    
    # Fetch all devices from ThingsBoard
    tb_devices = fetch_thingsboard_devices()
    
    # Categorize assets using config profile names
    countries, states, asset_devices = categorize_assets(assets, config)
    
    # Fetch asset relations to map states to countries
    THINGSBOARD_URL = config.get('thingsboard', 'url')
    JWT_TOKEN = config.get('thingsboard', 'jwt_token')
    HEADERS = {
        "Content-Type": "application/json",
        "X-Authorization": f"Bearer {JWT_TOKEN}"
    }
    
    relations = get_asset_relations(THINGSBOARD_URL, HEADERS)
    state_country_relations = find_state_country_mapping(states, countries, relations)
    
    # Display categorization for review
    print("\n📋 Asset Categorization:")
    print("Countries:")
    for country in countries:
        print(f"  - {country['name']} (Type: {country.get('type', 'N/A')})")
    
    print("States:")
    for state in states:
        print(f"  - {state['name']} (Type: {state.get('type', 'N/A')})")
    
    print("Other Assets (will be treated as devices):")
    for device in asset_devices[:10]:  # Show first 10 only
        print(f"  - {device['name']} (Type: {device.get('type', 'N/A')})")
    if len(asset_devices) > 10:
        print(f"  ... and {len(asset_devices) - 10} more")
    
    print(f"\nThingsBoard Devices:")
    for device in tb_devices[:10]:  # Show first 10 only
        print(f"  - {device['name']} (Label: {device.get('label', 'N/A')})")
    if len(tb_devices) > 10:
        print(f"  ... and {len(tb_devices) - 10} more")
    
    print(f"\n🔗 State-Country Relations Found: {len(state_country_relations)}")
    for state_id, country_id in state_country_relations.items():
        state_name = next((s['name'] for s in states if s['id']['id'] == state_id), 'Unknown')
        country_name = next((c['name'] for c in countries if c['id']['id'] == country_id), 'Unknown')
        print(f"  - {state_name} → {country_name}")
    
    # Ask for confirmation
    response = input("\n❓ Proceed with saving to database? (y/N): ")
    if response.lower() != 'y':
        print("❌ Operation cancelled by user.")
        return
    
    # Save to database with proper relationships
    print("\n💾 Saving to database...")
    country_mapping = save_countries_to_db(countries)
    state_mapping = save_states_to_db(states, country_mapping, state_country_relations)
    save_asset_devices_to_db(asset_devices, state_mapping, country_mapping)
    save_thingsboard_devices_to_db(tb_devices, state_mapping, country_mapping)
    
    print("\n✅ Asset and device extraction and database save completed!")
    print(f"📊 Summary: {len(countries)} countries, {len(states)} states, {len(asset_devices)} asset devices, {len(tb_devices)} ThingsBoard devices saved")

if __name__ == "__main__":
    main()