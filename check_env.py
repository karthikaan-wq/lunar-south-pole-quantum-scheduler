
import sys

import numpy
import scipy
import pandas
import fastapi
import uvicorn
import spiceypy
import pytest
import matplotlib

print("Python:", sys.version.split()[0])
print("NumPy:", numpy.__version__)
print("SciPy:", scipy.__version__)
print("Pandas:", pandas.__version__)
print("FastAPI:", fastapi.__version__)
print("Uvicorn:", uvicorn.__version__)
print("SpiceyPy:", spiceypy.__version__)
print("Pytest:", pytest.__version__)
print("Matplotlib:", matplotlib.__version__)

print("Virtual environment active:", sys.prefix != sys.base_prefix)
