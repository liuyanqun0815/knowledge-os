"""Domain ports package.

Import concrete modules directly, e.g.::

    from akos.domain.ports.knowledge import KnowledgePort

Avoid barrel imports here — eager re-exports create cycles with legacy shims
(``knowledge_base.__init__`` → ``ports`` → hub → ``knowledge_base.models``).
"""
