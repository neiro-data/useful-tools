"""Settings app for the Webpage Time Tracker userscript.

Owns `~/.webpage-time-tracker/config.json` and serves it on loopback so the
userscript can fetch and cache it instead of having its CONFIG block edited by
hand.
"""

__all__ = ["__version__"]

__version__ = "0.2.0"
