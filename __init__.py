import importlib
import pkgutil
import inspect
from typing import List
from backend.utils import get_logger
from backend.plugins.base import AuraPlugin

logger = get_logger("PluginLoader")

_plugin_registry: List[AuraPlugin] = []

def load_plugins():
    """Dynamically load plugins and instantiate them into the registry."""
    global _plugin_registry
    _plugin_registry.clear()
    
    import backend.plugins as plugins_pkg
    logger.info("Loading plugins...")
    
    for _, name, ispkg in pkgutil.iter_modules(plugins_pkg.__path__, plugins_pkg.__name__ + "."):
        try:
            module = importlib.import_module(name)
            # Find classes in the module that inherit from AuraPlugin
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if inspect.isclass(attr) and issubclass(attr, AuraPlugin) and attr is not AuraPlugin:
                    # Instantiate and register
                    _plugin_registry.append(attr())
                    logger.info(f"Registered plugin class: {attr.__name__} (Priority: {attr.priority})")
        except Exception as e:
            logger.error(f"Failed to load plugin {name}: {e}")
            
    # Sort registered plugins by priority
    _plugin_registry.sort(key=lambda p: p.priority)

def get_plugins() -> List[AuraPlugin]:
    return _plugin_registry
