"""Constants for the DroneMobile python library."""

AWSCLIENTID = "3l3gtebtua7qft45b4splbeuiu"

URLS = {
    "auth": "https://cognito-idp.us-east-1.amazonaws.com/",
    "user_info": "https://api.dronemobile.com/api/v1/user",
    "vehicle_info": "https://api.dronemobile.com/api/v1/vehicle?limit=",
    "command": "https://accounts.dronemobile.com/api/iot/send-command",
}

AVAILABLE_COMMANDS = {
    "trunk",
    "remote_start",
    "remote_stop",
    "arm",
    "disarm",
    "panic",
    "remote_aux1",
    "remote_aux2",
    "location",
}

COMMAND_HEADERS = {
    "x-drone-api": None,
    "Content-Type": "application/json;charset=utf-8",
}

AUTH_HEADERS = {
    "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
    "X-Amz-User-Agent": "aws-amplify/0.1.x js",
    "Content-Type": "application/x-amz-json-1.1",
}

TOKEN_FILE_LOCATION = "./drone_mobile_token.txt"