#!/usr/bin/env python

"""
Simple script to demo the API
"""

import sys, os, logging, time
from drone_mobile import Vehicle

if __name__ == "__main__":

    if len(sys.argv) != 3:
        raise Exception('You must specify Username and Password as arguments, e.g. demo.py test@test.com password123')
    else:            
        r = Vehicle(sys.argv[1], sys.argv[2]) # Username, Password

        print(r.status()) # Print the status of all vehicles

        # r.unlock() # Unlock the doors

        # time.sleep(10) # Wait 10 seconds

        # r.lock() # Lock the doors