#!/usr/bin/env python3
"""
Helper script to get JWT token from ThingsBoard
"""
import requests
import json
import configparser
import os

def get_jwt_token(base_url, username, password):
    """
    Get JWT token from ThingsBoard using username/password
    
    Args:
        base_url: ThingsBoard server URL
        username: Your ThingsBoard username
        password: Your ThingsBoard password
        
    Returns:
        JWT token string or None if failed
    """
    login_url = f"{base_url.rstrip('/')}/api/auth/login"
    
    payload = {
        "username": username,
        "password": password
    }
    
    try:
        response = requests.post(login_url, json=payload)
        response.raise_for_status()
        
        result = response.json()
        token = result.get('token')
        
        if token:
            print(f"✅ Successfully obtained JWT token")
            print(f"Token: {token}")
            return token
        else:
            print("❌ No token in response")
            return None
            
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP error: {e}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def update_config_with_token(token, config_file="config.properties"):
    """Update config.properties file with the JWT token"""
    config = configparser.ConfigParser()
    
    if os.path.exists(config_file):
        config.read(config_file)
    
    if 'thingsboard' not in config:
        config.add_section('thingsboard')
    
    config.set('thingsboard', 'jwt_token', token)
    
    with open(config_file, 'w') as f:
        config.write(f)
    
    print(f"✅ Updated {config_file} with JWT token")

if __name__ == "__main__":
    # Load current config
    config = configparser.ConfigParser()
    config.read("config.properties")
    
    base_url = config.get('thingsboard', 'url', fallback='https://thingsboard-poc.papayaparking.com')
    
    print(f"Getting JWT token from: {base_url}")
    print("Please enter your ThingsBoard credentials:")
    
    username = input("Username: ")
    password = input("Password: ")
    
    token = get_jwt_token(base_url, username, password)
    
    if token:
        update_config_with_token(token)
        print("\n🎉 Ready to use! You can now run your device service.")
    else:
        print("\n❌ Failed to get token. Please check your credentials and try again.")