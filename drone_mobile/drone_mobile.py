from .const import (
    URLS,
    AVAILABLE_COMMANDS,
    COMMAND_HEADERS,
    AUTH_HEADERS,
    AWSCLIENTID,
    TOKEN_FILE_LOCATION,
    HOST,
)

import json
import logging
import os
import time

import requests

_LOGGER = logging.getLogger(__name__)
defaultHeaders = {
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip",
}

class Vehicle(object):
    '''Represents a DroneMobile vehicle, with methods for status and issuing commands'''

    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.accessToken = None
        self.accessTokenExpiresIn = None
        self.accessTokenExpiresAt = None
        self.idToken = None
        self.idTokenType = None
        self.refreshToken = None
        self.token_location = TOKEN_FILE_LOCATION
    
    def auth(self):
        """Authenticate and store the token"""

        json = {
            "AuthFlow": "USER_PASSWORD_AUTH",
            "ClientId": AWSCLIENTID,
            "AuthParameters": {
                "USERNAME": self.username,
                "PASSWORD": self.password,
            },
            "ClientMetadata": {},
        }

        headers = {
            **defaultHeaders,
            **AUTH_HEADERS,
        }

        response = requests.post(
            URLS["auth"],
            json=json,
            headers=headers,
        )

        if response.status_code == 200:
            _LOGGER.debug("Succesfully fetched token.")
            result = response.json()
            self.accessToken = result["AuthenticationResult"]["AccessToken"]
            self.accessTokenExpiresAt = (time.time() - 100) + result["AuthenticationResult"]["ExpiresIn"]
            self.idToken = result["AuthenticationResult"]["IdToken"]
            self.idTokenType = result["AuthenticationResult"]["TokenType"]
            self.refreshToken = result["AuthenticationResult"]["RefreshToken"]
            result["expiry_date"] = (time.time() - 100) + result[
                "AuthenticationResult"
            ]["ExpiresIn"]
            self.writeToken(result)
            return True
        else:
            response.raise_for_status()
    
    def __acquireToken(self):
        # Fetch and refresh token as needed
        # If file exists read in token file and check it's valid
        if os.path.isfile(self.token_location):
            data = self.readToken()
        else:
            data = dict()
            data["AuthenticationResult"]["AccessToken"] = self.accessToken
            data["expiry_date"] = self.accessTokenExpiresAt
            data["AuthenticationResult"]["IdToken"] = self.idToken
            data["AuthenticationResult"]["TokenType"] = self.idTokenType
            data["AuthenticationResult"]["RefreshToken"] = self.refreshToken
        self.accessToken = data["AuthenticationResult"]["AccessToken"]
        self.accessTokenExpiresAt = data["expiry_date"]
        self.idToken = data["AuthenticationResult"]["IdToken"]
        self.idTokenType = data["AuthenticationResult"]["TokenType"]
        self.refreshToken = data["AuthenticationResult"]["RefreshToken"]
        if self.accessTokenExpiresAt:
            if time.time() >= self.accessTokenExpiresAt:
                _LOGGER.debug("No token, or has expired, requesting new token")
                self.__refreshToken()
        if self.idToken == None:
            # No existing token exists so refreshing library
            self.auth()
        else:
            _LOGGER.debug("Token is valid, continuing")
            pass

    def __refreshToken(self):
        # Token is invalid so let's try refreshing it
        json = {
            "AuthFlow": "REFRESH_TOKEN_AUTH",
            "ClientId": AWSCLIENTID,
            "AuthParameters": {
                "REFRESH_TOKEN": self.refreshToken,
            },
        }
        headers = {
            **defaultHeaders,
            **AUTH_HEADERS,
        }

        response = requests.post(
            URLS["auth"],
            json=json,
            headers=headers,
        )

        if response.status_code == 200:
            result = response.json()
            self.accessToken = result["AuthenticationResult"]["AccessToken"]
            self.accessTokenExpiresAt = (time.time() - 100) + result["AuthenticationResult"]["ExpiresIn"]
            self.idToken = result["AuthenticationResult"]["IdToken"]
            self.idTokenType = result["AuthenticationResult"]["TokenType"]
            if "RefreshToken" in result:
                self.refreshToken = result["AuthenticationResult"]["RefreshToken"]
            else:
                result["AuthenticationResult"]["RefreshToken"] = self.refreshToken
            self.writeToken(result)
        if response.status_code == 401:
            _LOGGER.debug("401 response while refreshing token")
            self.auth()
    
    def writeToken(self, token):
        # Save token to file to be reused
        with open(self.token_location, "w") as outfile:
            token["expiry_date"] = (time.time() - 100) + token["AuthenticationResult"]["ExpiresIn"]
            json.dump(token, outfile)

    def readToken(self):
        # Get saved token from file
        with open(self.token_location) as token_file:
            return json.load(token_file)

    def clearTempToken(self):
        if os.path.isfile("/tmp/droneMobile_token.txt"):
            os.remove("/tmp/droneMobile_token.txt")
        if os.path.isfile("/tmp/token.txt"):
            os.remove("/tmp/token.txt")

    def replaceToken(self):
        self.clearTempToken()
        if os.path.isfile(TOKEN_FILE_LOCATION):
            os.remove(TOKEN_FILE_LOCATION)
        self.auth()

    def status(self):
        # Get the status of the vehicles
        self.__acquireToken()

        commandHeaders = COMMAND_HEADERS
        commandHeaders['Authorization'] = f"{self.idTokenType} {self.idToken}"

        headers = {
            **defaultHeaders,
            **commandHeaders,
        }

        response = requests.get(
            URLS["vehicle_info"],
            headers=headers,
        )

        if response.status_code == 200:
            return response.json()["results"]
        else:
            response.raise_for_status()
    
    def device_status(self, deviceKey):
        """
        Poll the vehicle for updates
        """
        return self.sendCommand("DEVICE_STATUS", deviceKey, "2")

    def start(self, deviceKey):
        """
        Issue a start command to the engine
        """
        return self.sendCommand("REMOTE_START", deviceKey, "1")

    def stop(self, deviceKey):
        """
        Issue a stop command to the engine
        """
        return self.sendCommand("REMOTE_STOP", deviceKey, "1")

    def lock(self, deviceKey):
        """
        Issue a lock command to the doors
        """
        return self.sendCommand("ARM", deviceKey, "1")

    def unlock(self, deviceKey):
        """
        Issue an unlock command to the doors
        """
        return self.sendCommand("DISARM", deviceKey, "1")

    def trunk(self, deviceKey):
        """
        Issue a command to open the trunk
        """
        return self.sendCommand("TRUNK", deviceKey, "1")
    
    def panic_on(self, deviceKey):
        """
        Issue a panic command to the vehicle
        """
        return self.sendCommand("PANIC_ON", deviceKey, "1")

    def panic_off(self, deviceKey):
        """
        Issue a panic command to the vehicle
        """
        return self.sendCommand("PANIC_OFF", deviceKey, "1")

    def aux1(self, deviceKey):
        """
        Issue a command to trigger the mapped Aux1 button event
        """
        return self.sendCommand("REMOTE_AUX1", deviceKey, "1")

    def aux2(self, deviceKey):
        """
        Issue a command to trigger the mapped Aux1 button event
        """
        return self.sendCommand("REMOTE_AUX2", deviceKey, "1")

    def location(self, deviceKey):
        """
        Issue a command to return the vehicle's current location
        """
        return self.sendCommand("LOCATION", deviceKey, "1")

    def sendCommand(self, command, deviceKey, deviceType):
        self.__acquireToken()

        commandHeaders = COMMAND_HEADERS
        commandHeaders['Authorization'] = f"{self.idTokenType} {self.idToken}"

        json = {
            "device_key": deviceKey,
            "command": command,
            "device_type":deviceType,
        }

        headers = {
            **defaultHeaders,
            **commandHeaders,
        }

        command = requests.post(
            URLS["command"],
            json=json,
            headers=headers,
        )

        if command.status_code == 200:
            return command.json()["parsed"]
        else:
            command.raise_for_status()
