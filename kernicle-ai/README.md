# Kernicle AI Plugin

**AI-powered analysis plugin for Kernicle** - adds intelligent diagnostics, fix recommendations, and resource links to your crash reports.

## Features

- 🤖 **Automatic AI Analysis** - No flags needed, just install and it works
- 🔧 **Fix Recommendations** - Actionable steps to resolve issues
- 📚 **Resource Links** - Relevant Stack Overflow, Reddit, Arch Wiki links
- 🆓 **Free LLM APIs** - Uses Groq (primary) and Gemini (fallback)
- 📖 **Built-in Knowledge Base** - Works offline for common issues

## Installation

```bash
# Install the plugin
pip install kernicle-ai

# Set your API key (get free from console.groq.com)
export GROQ_API_KEY="gsk_your_key_here"

# Optional: Gemini fallback (get from aistudio.google.com)
export GEMINI_API_KEY="your_key_here"
```

## Usage

Once installed, Kernicle automatically includes AI analysis in reports:

```bash
# Regular kernicle commands now include AI insights
kernicle push --range "last:5m" --all

# Export with AI-enhanced report
kernicle export session-20260103-120000 --format html
```

## Example Output

```
╭─────────────────────────────────────────────────────────────╮
│ 🤖 AI ANALYSIS                                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ 📋 DIAGNOSIS:                                               │
│ Kernel panic caused by spinlock deadlock in kworker thread. │
│ Root cause: Race condition in network driver during high    │
│ traffic load.                                               │
│                                                             │
│ 🔧 RECOMMENDED FIXES:                                       │
│ 1. Update kernel: sudo apt upgrade linux-image-generic      │
│ 2. Update network driver: sudo apt install --reinstall      │
│    linux-modules-extra-$(uname -r)                          │
│ 3. Check for firmware updates for your NIC                  │
│                                                             │
│ 📚 RESOURCES:                                               │
│ • Kernel Panic Debugging Guide (Arch Wiki)                  │
│ • Similar issue discussion (Reddit r/linux)                 │
│ • Network driver troubleshooting (Ask Ubuntu)               │
│                                                             │
│ 🏥 SYSTEM HEALTH: ⚠️ NEEDS ATTENTION                        │
│ Memory pressure detected (92% used), consider adding swap   │
│ or investigating memory leaks.                              │
│                                                             │
╰─────────────────────────────────────────────────────────────╯
```

## Configuration

Set via environment variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `GROQ_API_KEY` | Groq API key (free) | Yes* |
| `GEMINI_API_KEY` | Google Gemini API key | No (fallback) |
| `KERNICLE_AI_PROVIDER` | Force provider: `groq`, `gemini`, `offline` | No |
| `KERNICLE_AI_SEARCH` | Enable web search: `true`/`false` | No (default: true) |

*If no API key is set, the built-in knowledge base is used (offline mode).

## Get Free API Keys

1. **Groq** (Recommended): https://console.groq.com
   - Instant signup, 14,400 tokens/min free

2. **Google Gemini**: https://aistudio.google.com
   - Google account required, 60 requests/min free

## License

MIT
