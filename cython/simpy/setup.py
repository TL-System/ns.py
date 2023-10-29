#!/usr/bin/env python
from setuptools import setup, Extension

try:
    from Cython.Build import cythonize

    ext_modules = cythonize(
        [
            Extension("simpy.core", ["simpy/core.py"]),
            Extension("simpy.events", ["simpy/events.py"]),
            Extension("simpy.exceptions", ["simpy/exceptions.py"]),
            Extension("simpy.rt", ["simpy/rt.py"]),
            Extension("simpy.util", ["simpy/util.py"]),
            Extension("simpy.resources.base", ["simpy/resources/base.py"]),
            Extension("simpy.resources.container", ["simpy/resources/container.py"]),
            Extension("simpy.resources.resource", ["simpy/resources/resource.py"]),
            Extension("simpy.resources.store", ["simpy/resources/store.py"]),
        ],
        language_level=3,
    )
except ImportError:
    ext_modules = None

setup(ext_modules=ext_modules)
