"""Pin python3 to match hostpython3==3.11.11 (p4a master defaults to 3.14)."""

from pythonforandroid.recipes.python3 import Python3Recipe as _Python3Recipe


class Python3Recipe(_Python3Recipe):
    version = "3.11.11"


recipe = Python3Recipe()
