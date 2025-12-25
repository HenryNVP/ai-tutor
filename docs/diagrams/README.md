# Architecture Diagrams

PlantUML source files for system architecture diagrams.

## Files

- **architecture.puml** - Overall system architecture
- **components.puml** - Multi-agent orchestration (multiple diagrams)
- **session_management.puml** - Session management and API flows

## Rendering Diagrams

### Quick Command

```bash
# From project root
cd docs/diagrams
java -jar plantuml-mit-1.2025.9.jar *.puml
```

### Alternative: Using PlantUML CLI

```bash
# If PlantUML is installed
plantuml docs/diagrams/*.puml
```

### Output

Generated PNG files will be created in `docs/diagrams/`:
- `architecture.png`
- `components.png` (contains multiple diagrams)
- `session_management.png` (contains multiple diagrams)

## Notes

- Diagrams reflect current implementation
- Update diagrams when architecture changes
- PNG files are generated outputs (can be regenerated)

