[![Build Status](https://travis-ci.org/ebranlard/welib.svg?branch=master)](https://travis-ci.org/ebranlard/welib)

# welib

Wind energy library, suite of matlab and python tools.


See also:

- [weio](http://github.com/ebranlard/weio/) library to read and write files used in wind energy

- [pyDatView](http://github.com/ebranlard/pyDatView/): GUI to visualize files (supported by weio) and perform analyses on the data



# Installation and testing
```bash
git clone --recurse-submodules http://github.com/ebranlard/welib
cd welib
python -m pip install -r requirements.txt
python -m pip install -e .
pytest
```


# Examples
Check out the examples folder for examples. Some are listed below:

- Manipulation of airfoil curves (see `welib\airfoils\examples\`)
- Dynamic stall model by Oye and Morten Hansen (see `welib\airfoils\examples\`)


# Libraries

- Airfoils: polar manipulations, dynamic stall models
- BEM: steady and unsteady bem code

