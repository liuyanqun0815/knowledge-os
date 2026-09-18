from akos.interfaces.api.admin_api.routes_evolution import router as evolution_router
from akos.interfaces.api.admin_api.routes_knowledge_bases import router as knowledge_bases_router
from akos.interfaces.api.admin_api.routes_sources import router as sources_router

__all__ = ["evolution_router", "knowledge_bases_router", "sources_router"]
