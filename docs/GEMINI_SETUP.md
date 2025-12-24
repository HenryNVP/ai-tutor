# Gemini Setup for Note Agent

## Overview

The Note Agent can use Google Gemini (via LiteLLM) for processing entire documents with its 1M token context window, eliminating the need for chunking and retrieval for summarization tasks.

## Quick Start

### 1. Install LiteLLM

```bash
pip install "openai-agents[litellm]"
```

### 2. Get Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Set it as an environment variable:

```bash
export GEMINI_API_KEY="your-api-key-here"
```

### 3. Configure Note Agent

Edit `config/default.yaml`:

```yaml
note_agent:
  model: "gemini/gemini-1.5-pro"  # or "gemini/gemini-1.5-flash" for faster/cheaper
  api_key: null  # Uses GEMINI_API_KEY env var if null
  use_full_context: true
```

### 4. Restart the Application

The Note Agent will now use Gemini for summarization tasks.

## Model Options

| Model | Context Window | Speed | Cost | Best For |
|-------|---------------|-------|------|----------|
| `gemini/gemini-1.5-pro` | 1M tokens | Slower | Higher | Best quality, complex documents |
| `gemini/gemini-1.5-flash` | 1M tokens | Faster | Lower | Fast, cost-effective summaries |
| `null` (default) | 128k tokens | Fast | Low | Small documents, fallback |

## Usage Examples

### Summarize a Document

```
User: "Summarize the uploaded file"
```

The Note Agent will:
1. Fetch the full document (all chunks)
2. Send entire document to Gemini (if configured)
3. Generate comprehensive summary with full context

### Create Notes

```
User: "Create notes from Lecture7.pdf"
```

Gemini processes the entire document, maintaining structure and relationships.

## Fallback Behavior

If Gemini is not available (no API key, LiteLLM not installed, or API error), the system automatically falls back to:
- Default model (`gpt-4o-mini`)
- Existing retrieval-based approach

No code changes needed - just graceful degradation.

## Configuration Options

### Via Config File

```yaml
note_agent:
  model: "gemini/gemini-1.5-pro"
  api_key: "your-key-here"  # Optional, can use env var instead
  use_full_context: true
```

### Via Environment Variable

```bash
export GEMINI_API_KEY="your-api-key"
# Then set model in config file
```

## Cost Considerations

- **Gemini 1.5 Pro**: ~$1.25-$5 per 1M input tokens
- **Gemini 1.5 Flash**: ~$0.075-$0.30 per 1M input tokens
- **GPT-4o-mini** (default): ~$0.15-$0.60 per 1M tokens

For large documents (>100k tokens), Gemini can be more cost-effective due to single API call vs multiple retrievals.

## Troubleshooting

### "LiteLLM not installed"

```bash
pip install "openai-agents[litellm]"
```

### "GEMINI_API_KEY not found"

Set the environment variable:
```bash
export GEMINI_API_KEY="your-key"
```

Or provide it in config:
```yaml
note_agent:
  api_key: "your-key-here"
```

### Model falls back to default

Check logs for warnings. Common causes:
- API key not set
- LiteLLM not installed
- Invalid model name (must start with `gemini/`)

## Example Config

See `config/gemini_example.yaml` for a complete example configuration.

