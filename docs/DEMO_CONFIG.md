# Demo Configuration Guide

## Overview

The demo configuration (`config/demo.yaml`) provides a minimal setup for showcasing RAG capabilities with simplified settings.

## Configuration Files

### `config/default.yaml` (Default)
- Full configuration with all options
- Demo mode enabled by default (`demo_mode: true`)
- Suitable for both demo and production use

### `config/demo.yaml` (Minimal)
- Minimal configuration with essential settings only
- Demo mode enabled
- Easier to understand and modify
- Perfect for quick demos

## Using Demo Config

### Option 1: Use Default Config (Recommended)
The default config already has demo mode enabled:
```bash
streamlit run apps/ui.py
# Uses config/default.yaml with demo_mode: true
```

### Option 2: Use Demo Config File
Explicitly use the minimal demo config:
```python
from ai_tutor.system import TutorSystem

# Load demo config
system = TutorSystem.from_config('config/demo.yaml')
```

### Option 3: Environment Variable Override
Override specific settings via environment:
```bash
export AI_TUTOR_CONFIG_OVERRIDES='{"demo_mode": true, "model": {"temperature": 0.7}}'
```

## Demo Config Contents

The demo config (`config/demo.yaml`) includes:

### Essential Settings
- **Model**: `gpt-4o-mini` (fast, cost-effective)
- **Embeddings**: `BAAI/bge-base-en` (local, no API calls)
- **Chunking**: Balanced settings (500 tokens, 80 overlap)
- **Retrieval**: Top 5 results per query
- **Demo Mode**: Enabled (disables personalization)

### Simplified Settings
- **Logging**: INFO level (less verbose)
- **Paths**: Standard data directories
- **Course Defaults**: Basic values (not used in demo mode)

## What Demo Mode Does

When `demo_mode: true`:

### Disabled
- ❌ Personalization system (no profile loading/saving)
- ❌ Adaptive difficulty adjustment
- ❌ Style selection based on mastery
- ❌ Progress tracking

### Enabled
- ✅ All core RAG features (Q&A, quiz, notes)
- ✅ Document ingestion
- ✅ Source-filtered retrieval
- ✅ Data visualization
- ✅ Static "stepwise" style (balanced)

## Comparison

| Feature | Default Config | Demo Config |
|---------|---------------|-------------|
| Demo Mode | ✅ Enabled | ✅ Enabled |
| Settings | Full (all options) | Minimal (essentials) |
| Comments | Detailed | Essential only |
| Use Case | Production + Demo | Demo only |

## Customization

To customize the demo config:

1. **Copy demo.yaml**:
   ```bash
   cp config/demo.yaml config/my_demo.yaml
   ```

2. **Modify settings**:
   ```yaml
   model:
     temperature: 0.8  # More creative responses
   
   retrieval:
     top_k: 10  # More results per query
   ```

3. **Use custom config**:
   ```python
   system = TutorSystem.from_config('config/my_demo.yaml')
   ```

## Quick Start with Demo Config

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set API key
export OPENAI_API_KEY=your_key_here

# 3. Run with demo config (if modifying code)
# Or just use default.yaml (demo mode already enabled)
streamlit run apps/ui.py
```

## Benefits

1. **Simpler Setup**: Minimal configuration, easy to understand
2. **Faster Startup**: No personalization initialization
3. **Consistent Behavior**: Same experience for all users
4. **Focus on RAG**: Highlights core capabilities

## Production Use

For production, set `demo_mode: false` in `config/default.yaml`:
```yaml
demo_mode: false  # Enable full personalization
```

This enables:
- Adaptive learning
- Progress tracking
- Personalized difficulty
- Style selection based on mastery

