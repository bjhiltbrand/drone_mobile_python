[![PyPI version](https://badge.fury.io/py/drone_mobile.svg)](https://badge.fury.io/py/drone_mobile)

# drone_mobile-python

This is a basic Python wrapper around the DroneMobile API. The wrapper provides methods to return vehicle status as well as some basic commands, e.g. start/stop, lock/unlock.

## Features

* Automatically authenticate & re-fetch tokens once expired
* Get status of the vehicle (this returns a ton of info about the car: lat/long, temperature, battery, odometer, door status, and a bunch of other stuff that may/may not apply to your car.
* Start the engine
* Stop the engine
* Lock the doors
* Unlock the doors

## Install
Install using pip:

```
pip install drone_mobile
```

## Demo

To test the libary there is a demo script `demo.py`.

```
demo.py USERNAME PASSWORD
```

e.g.

```
demo.py test@test.com mypassword
```

## Publishing new versions of this package

1. Bump the version number inside `setup.py`.
2. Build the package: `python setup.py sdist bdist_wheel`.
3. Upload to TestPyPi using `twine upload --repository-url https://test.pypi.org/legacy/ dist/*` and verify everything is as expected.
4. Upload to PyPi using `twine upload dist/*`.
5. All done!