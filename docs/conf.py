"""
Sphinx configuration for the Greeting project.
"""
import os
import sys

# Make the src package importable during doc builds
sys.path.insert(0, os.path.abspath("../src"))

# -- Project info ------------------------------------------------------------
project   = "Greeting"
author    = "Dev"
release   = "1.3.0"

# -- General config ----------------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",       # pull docstrings from source automatically
    "sphinx.ext.napoleon",      # support Google / NumPy docstring styles
    "sphinx.ext.viewcode",      # add [source] links next to each item
]

# autodoc: show members in source order, include private members prefixed with _
autodoc_default_options = {
    "members":          True,
    "undoc-members":    False,
    "show-inheritance": True,
}

templates_path   = ["_templates"]
exclude_patterns = ["_build"]

# -- HTML output -------------------------------------------------------------
html_theme = "sphinx_rtd_theme"
