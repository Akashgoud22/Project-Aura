from typing import Any, Dict

class AuraPlugin:
    """Base class for Aura AI plugins."""
    
    # Lower priority number = executes first
    priority: int = 100 
    
    async def can_handle(self, command: str, intent: str) -> bool:
        """Return True if this plugin can handle the intent/command."""
        raise NotImplementedError
        
    async def execute(self, payload: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the plugin logic.
        Should return a dict like:
        {"success": True/False, "response": "Message to speak", "error": "Optional error msg"}
        """
        raise NotImplementedError
