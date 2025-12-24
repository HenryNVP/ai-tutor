# AI Tutor Agents

This directory contains the implementation of the 6 specialized agents used in the AI Tutor system.

## Agents

- **QA Agent** (`qa.py`) - Retrieval-augmented Q&A
- **Quiz Agent** (`quiz_agent.py`) - Quiz generation
- **Note Agent** (`note.py`) - Study notes and summaries
- **Visualization Agent** (`viz_agent.py`) - Data visualizations
- **Web Agent** (`web.py`) - Web search and current events
- **Ingestion Agent** (`ingestion.py`) - Document processing

## Core Files

- `tutor.py` - Multi-agent coordinator (`TutorAgent`)
- `routing.py` - Keyword-based routing logic
- `retrieval_tools.py` - Shared retrieval tools

## Documentation

For detailed documentation on each agent, routing, and usage examples, see:
- **[docs/AGENTS.md](../../../docs/AGENTS.md)** - Complete agent documentation
- **[docs/MANUAL_TESTING.md](../../../docs/MANUAL_TESTING.md)** - Testing guide
- **[docs/ARCHITECTURE.md](../../../docs/ARCHITECTURE.md)** - System architecture

## Development

When adding or modifying agents:
1. Follow the existing pattern (see `qa.py` or `note.py`)
2. Use `build_*_agent()` function pattern
3. Register in `TutorAgent._build_agents()`
4. Add routing keywords in `routing.py`
5. Update `docs/AGENTS.md` with changes

