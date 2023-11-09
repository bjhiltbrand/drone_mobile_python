"""Constants for the DroneMobile python library."""

AWSCLIENTID = "3l3gtebtua7qft45b4splbeuiu"

BASE_API_URL = "https://api.dronemobile.com/api/"

HOST = "api.dronemobile.com"

API_VERSION = "v1"

URLS = {
    "auth": "https://cognito-idp.us-east-1.amazonaws.com/",
    "user_info": f"{BASE_API_URL}{API_VERSION}/user",
    "vehicle_info": f"{BASE_API_URL}{API_VERSION}/vehicle?limit=100",
    "command": f"{BASE_API_URL}{API_VERSION}/iot/command",
}

AVAILABLE_COMMANDS = {
    "DEVICE_STATUS",
    "REMOTE_START",
    "REMOTE_STOP",
    "ARM",
    "DISARM",
    "TRUNK",
    "PANIC_ON",
    "PANIC_OFF",
    "REMOTE_AUX1",
    "REMOTE_AUX2",
    "LOCATION",
}

AVAILABLE_DEVICE_TYPES = {
    "1", # I think this is in reference to the vehicle
    "2", # I think this is in reference to the DroneMobile Contoller Module
}

COMMAND_HEADERS = {
    "Authorization": None,
    "Content-Type": "application/json",
}

AUTH_HEADERS = {
    "Referer": "https://accounts.dronemobile.com/",
    "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
    "X-Amz-User-Agent": "aws-amplify/5.0.4 js",
    "Content-Type": "application/x-amz-json-1.1",
}

TOKEN_FILE_LOCATION = "./drone_mobile_token.txt"