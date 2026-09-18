def test_application_hub_identity():
    from akos.application.ask.synthesis import build_synthesis_context as AskHub
    from akos.application.evolution.service import EvolutionService as EvoHub
    from akos.application.ingest.service import KnowledgeCompiler as IngestHub
    from akos.application.wiki.compile import compile_topics_for_source as WikiHub
    from compiler.service import KnowledgeCompiler as IngestShim
    from evolution.service import EvolutionService as EvoShim
    from orchestrator.synthesis import build_synthesis_context as AskShim
    from wiki.compile import compile_topics_for_source as WikiShim

    assert WikiHub is WikiShim
    assert IngestHub is IngestShim
    assert EvoHub is EvoShim
    assert AskHub is AskShim
