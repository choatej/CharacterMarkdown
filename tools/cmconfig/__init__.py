"""cmconfig: the configuration tree for CharacterMarkdown exports. See data/config/README.md."""

from .legacy import read_lua_defaults
from .model import ConfigCollection, ConfigData, ConfigItem

__all__ = ["ConfigCollection", "ConfigData", "ConfigItem", "read_lua_defaults"]
