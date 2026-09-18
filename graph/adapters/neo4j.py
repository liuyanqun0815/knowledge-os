"""Backward-compatible shim — prefer ``akos.adapters.graph.neo4j``."""

from akos.adapters.graph.neo4j import Neo4jGraph

__all__ = ["Neo4jGraph"]
