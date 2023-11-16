#!/usr/bin/env python

"""
Simple script to demo the API
"""

import sys, json, pprint
from drone_mobile import Vehicle

if __name__ == "__main__":
        if len(sys.argv) != 3:
                raise Exception('You must specify Username and Password as arguments, e.g. demo.py test@test.com password123')
        else:
                vehicleObject = Vehicle(sys.argv[1], sys.argv[2]) # Username, Password   
                vehicleObject.auth()        
                vehicles = vehicleObject.getAllVehicles()

                pprint.pprint(json.dumps(vehicles), compact=True)# Print the status of all vehicles
                
                # r.unlock() # Unlock the doors

                # time.sleep(10) # Wait 10 seconds

                # r.lock() # Lock the doors