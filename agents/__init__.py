# agents/__init__.py
# Package agents ResilientFlow AI
# Chaque agent est indépendant et peut être développé séparément.

from .agent_lionel  import run_agent_lionel
from .agent_sophie  import run_agent_sophie
from .agent_antoine import run_agent_antoine
from .agent_leila   import run_agent_leila

__all__ = [
    "run_agent_lionel",
    "run_agent_sophie",
    "run_agent_antoine",
    "run_agent_leila",
]
