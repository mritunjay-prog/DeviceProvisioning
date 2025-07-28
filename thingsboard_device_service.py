import requests
import json
from typing import Dict, Optional, Any
from dataclasses import dataclass
import logging
import configparser
import os
import socket

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class DeviceProfileId:
    entityType: str = "DEVICE_PROFILE"
    id: str = ""

@dataclass
class AdditionalInfo:
    gateway: bool = False
    overwriteActivityTime: bool = False
    description: str = ""

@dataclass
class DevicePayload:
    name: str
    label: str = ""
    deviceProfileId: DeviceProfileId = None
    additionalInfo: AdditionalInfo = None
    
    def __post_init__(self):
        if self.deviceProfileId is None:
            self.deviceProfileId = DeviceProfileId()
        if self.additionalInfo is None:
            self.additionalInfo = AdditionalInfo()

class ThingsBoardDeviceService:
    def __init__(self, config_file: str = "config.properties", base_url: str = None, auth_token: str = None):
        # Load configuration
        self.config = configparser.ConfigParser()
        if os.path.exists(config_file):
            self.config.read(config_file)
        
        # Set configuration values with fallbacks
        self.base_url = (base_url or 
                        self.config.get('thingsboard', 'url', fallback='https://demo.thingsboard.io')).rstrip('/')
        self.default_device_profile_id = self.config.get('thingsboard', 'device_profile_id', 
                                                        fallback='75c7fab0-6529-11f0-8543-cf220f4e0102')
        # Get local hostname as device name
        local_hostname = socket.gethostname()
        self.default_device_name = self.config.get('thingsboard', 'device_name', 
                                                  fallback=local_hostname)
        
        # API endpoints
        self.device_endpoint = self.config.get('api', 'device_endpoint', fallback='/api/device')
        self.tenant_devices_endpoint = self.config.get('api', 'tenant_devices_endpoint', fallback='/api/tenant/devices')
        
        # Settings
        self.default_page_size = self.config.getint('settings', 'default_page_size', fallback=10)
        self.request_timeout = self.config.getint('settings', 'request_timeout', fallback=30)
        
        # JWT Token - use parameter first, then config, then None
        self.auth_token = auth_token or self.config.get('thingsboard', 'jwt_token', fallback=None)
        
        self.session = requests.Session()
        self.session.timeout = self.request_timeout
        
        # Set JWT token if available
        if self.auth_token and self.auth_token != 'your_jwt_token_here':
            self.session.headers.update({
                'Authorization': f'Bearer {self.auth_token}',
                'Content-Type': 'application/json'
            })
    
    def set_auth_token(self, token: str):
        """Set authentication token for API requests"""
        self.auth_token = token
        self.session.headers.update({
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        })
    

    
    def provision_device(self, device_name: str = None, device_profile_id: str = None, 
                        label: str = "", description: str = "", 
                        gateway: bool = False, overwrite_activity_time: bool = False) -> Dict[str, Any]:
        """
        Provision a new device in ThingsBoard
        
        Args:
            device_name: Name of the device (uses config default if not provided)
            device_profile_id: Device profile ID (uses config default if not provided)
            label: Device label (optional)
            description: Device description (optional)
            gateway: Whether device is a gateway (default: False)
            overwrite_activity_time: Whether to overwrite activity time (default: False)
            
        Returns:
            Dict containing the API response
        """
        
        # Use default device name from config if none provided
        if device_name is None:
            device_name = self.default_device_name
            
        # Use default device profile ID from config if none provided
        if device_profile_id is None:
            device_profile_id = self.default_device_profile_id
        
        payload = {
            "name": device_name,
            "label": label,
            "deviceProfileId": {
                "entityType": "DEVICE_PROFILE",
                "id": device_profile_id
            },
            "additionalInfo": {
                "gateway": gateway,
                "overwriteActivityTime": overwrite_activity_time,
                "description": description
            }
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}{self.device_endpoint}",
                json=payload
            )
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Device '{device_name}' provisioned successfully")
            return {
                "success": True,
                "data": result,
                "message": f"Device '{device_name}' created successfully"
            }
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP error occurred: {e}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "status_code": response.status_code
            }
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Request error occurred: {e}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
            
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
    
    def get_device(self, device_id: str) -> Dict[str, Any]:
        """
        Get device information by ID
        
        Args:
            device_id: Device ID
            
        Returns:
            Dict containing device information
        """
        try:
            response = self.session.get(f"{self.base_url}{self.device_endpoint}/{device_id}")
            response.raise_for_status()
            
            return {
                "success": True,
                "data": response.json()
            }
            
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def delete_device(self, device_id: str) -> Dict[str, Any]:
        """
        Delete a device by ID
        
        Args:
            device_id: Device ID to delete
            
        Returns:
            Dict containing operation result
        """
        try:
            response = self.session.delete(f"{self.base_url}{self.device_endpoint}/{device_id}")
            response.raise_for_status()
            
            logger.info(f"Device {device_id} deleted successfully")
            return {
                "success": True,
                "message": f"Device {device_id} deleted successfully"
            }
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to delete device {device_id}: {e}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
    
    def list_devices(self, page_size: int = 10, page: int = 0) -> Dict[str, Any]:
        """
        List devices with pagination
        
        Args:
            page_size: Number of devices per page
            page: Page number (0-based)
            
        Returns:
            Dict containing list of devices
        """
        try:
            params = {
                "pageSize": page_size,
                "page": page
            }
            
            response = self.session.get(
                f"{self.base_url}{self.tenant_devices_endpoint}",
                params=params
            )
            response.raise_for_status()
            
            return {
                "success": True,
                "data": response.json()
            }
            
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e)
            }


# Example usage and helper functions
def create_device_service(auth_token: str, base_url: str = "https://demo.thingsboard.io") -> ThingsBoardDeviceService:
    """
    Factory function to create a configured device service
    
    Args:
        auth_token: JWT authentication token
        base_url: ThingsBoard server URL
        
    Returns:
        Configured ThingsBoardDeviceService instance
    """
    return ThingsBoardDeviceService(base_url=base_url, auth_token=auth_token)


if __name__ == "__main__":
    # Example usage with config.properties file and JWT token
    
    # Initialize service with config file (JWT token loaded from config)
    service = ThingsBoardDeviceService()
    
    # Check if JWT token is configured
    if service.auth_token:
        print("JWT token loaded from config.properties")
        
        # Example 1: Provision device using defaults from config (both name and profile ID)
        print(f"\nProvisioning device with defaults from config...")
        print(f"Default device name: {service.default_device_name}")
        print(f"Default device profile ID: {service.default_device_profile_id}")
        result1 = service.provision_device(
            label="Sample Device",
            description="Device created with config defaults"
        )
        print("Result 1:", json.dumps(result1, indent=2))
        
        # Example 2: Provision device with custom name but default profile ID
        print("\nProvisioning device with custom name...")
        result2 = service.provision_device(
            device_name="SD_Custom_Device",
            label="Custom Named Device",
            description="Device with custom name but default profile"
        )
        print("Result 2:", json.dumps(result2, indent=2))
        
        # Example 3: Provision device with both custom name and profile ID
        print("\nProvisioning device with custom name and profile ID...")
        result3 = service.provision_device(
            device_name="SD_Fully_Custom",
            device_profile_id="75c7fab0-6529-11f0-8543-cf220f4e0102",
            label="Fully Custom Device",
            description="Device with custom name and profile"
        )
        print("Result 3:", json.dumps(result3, indent=2))
        
        # Example 3: List devices
        print("\nListing devices...")
        devices = service.list_devices(page_size=5)
        print("Devices:", json.dumps(devices, indent=2))
        
        # Example 4: Get device details (if device was created successfully)
        if result1["success"] and "data" in result1 and "id" in result1["data"]:
            device_id = result1["data"]["id"]["id"]
            print(f"\nGetting device details for ID: {device_id}")
            device_details = service.get_device(device_id)
            print("Device details:", json.dumps(device_details, indent=2))
        
    else:
        print("No JWT token found!")
        print("Please update your config.properties file with a valid JWT token:")
        print("1. Set jwt_token=your_actual_jwt_token in the [thingsboard] section")
        print("2. Or use service.set_auth_token('your_jwt_token') to set it manually")
        
        # Example of manual token setting
        print("\nExample of manual token setting:")
        print("service.set_auth_token('your_jwt_token_here')")
        print("result = service.provision_device(device_name='SD_Manual')")
        
        # Demonstrate service creation with manual token
        print("\nAlternatively, create service with token parameter:")
        print("service = ThingsBoardDeviceService(auth_token='your_jwt_token')")
        print("Or use the factory function:")
        print("service = create_device_service('your_jwt_token')")