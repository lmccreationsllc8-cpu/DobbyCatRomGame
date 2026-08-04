"""Pin hostpython3 to match python3==3.11.11 (p4a master defaults to 3.14)."""

from pythonforandroid.recipes.hostpython3 import HostPython3Recipe as _HostPython3Recipe


class HostPython3Recipe(_HostPython3Recipe):
    version = "3.11.11"


recipe = HostPython3Recipe()
