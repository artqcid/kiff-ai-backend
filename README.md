# KIFF AI Backend

FastAPI Backend for the KIFF LangChain Agent with RAG, MCP integration, and LLM orchestration.

## Features

- 🚀 FastAPI with OpenAPI/Swagger documentation
- 💬 Chat orchestration with llama.cpp integration
- 🔍 RAG (Retrieval-Augmented Generation) with Qdrant
- 🌐 MCP (Model Context Protocol) for web context fetching
- 📁 Document management and processing
- ⚙️ Profile and configuration management
- 🏷️ @tag-based context injection for business knowledge

## MCP Web Context System

The backend includes an integrated MCP (Model Context Protocol) system that fetches and caches web content to provide business context to the LLM.

### Features

- **@tag Syntax**: Use `@tagname` in chat messages to automatically fetch relevant web contexts
- **Smart Caching**: 14-day cache with automatic TTL management
- **Rate Limiting**: 10 requests/minute per domain to avoid overwhelming servers
- **Error Resilient**: Failed fetches don't block chat responses

### Available Context Sets

The system includes 21+ KIFF-specific context sets:

- **Office**: `@word`, `@excel`, `@google_docs`, `@google_sheets`, `@google_workspace`
- **Process**: `@camunda`, `@bpmn`
- **Swiss Business**: `@schweizer_vereinswesen`, `@vereins_vorstand`
- **Event Tech**: `@event_technik`, `@audio_technik`, `@netzwerk_technik`
- **Hospitality**: `@gastronomie`, `@bar`, `@restaurant_konzept`, `@bar_konzept`
- **Operations**: `@security`, `@betriebswirtschaft`, `@betriebskonzept`
- **Marketing**: `@event_produktion`, `@event_marketing`

### Usage Example

```bash
# Chat message with context injection
POST /api/v1/chat/messages
{
  "message": "Ich brauche Tipps für @gastronomie und @bar Konzepte in der Schweiz",
  "profile": "kiff"
}

# System automatically:
# 1. Detects @gastronomie and @bar tags
# 2. Fetches relevant URLs (gastrosuisse.ch, etc.)
# 3. Caches content for 14 days
# 4. Injects context into LLM prompt
```

### MCP Admin Endpoints

- `GET /api/v1/mcp/context-sets` - List all available context sets
- `GET /api/v1/mcp/cache/stats` - Get cache statistics
- `DELETE /api/v1/mcp/cache` - Clear entire cache
- `DELETE /api/v1/mcp/cache/{context_set}` - Clear cache for specific set
- `POST /api/v1/mcp/context-sets/reload` - Reload context sets from JSON
- `GET /api/v1/mcp/health` - MCP system health check

### Configuration

Context sets are defined in `backend/config/context_sets_kiff.json`:

```json
{
  "@gastronomie": {
    "urls": [
      "https://www.gastrosuisse.ch/",
      "https://www.kmu.admin.ch/"
    ]
  }
}
```

Cache is stored in `backend/cache/` (gitignored).

## Tech Stack

- Python 3.11+
- FastAPI
- Pydantic (Type safety)
- Qdrant (Vector database)
- llama.cpp (LLM inference)

## Project Structure

```
backend/
├── api/              # FastAPI application
│   ├── main.py       # App entry point
│   └── v1/           # API v1 endpoints
│       ├── chat.py
│       ├── config.py
│       ├── documents.py
│       ├── health.py
│       ├── mcp.py       # MCP admin endpoints
│       └── server.py
├── core/             # Business logic
│   ├── llm_client.py
│   ├── profile_agent.py
│   ├── web_context_service.py    # Web fetching & caching
│   └── context_manager.py        # Context set management
├── config/           # Configuration files
│   └── context_sets_kiff.json    # KIFF business contexts
├── cache/            # Web content cache (gitignored)
├── adapters/         # External integrations
└── README.md
```

## Development

### Prerequisites

- Python 3.11 or higher
- Virtual environment (venv)

### Setup

```bash
# Create and activate virtual environment (in main project root)
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows
# or
source venv/bin/activate     # Linux/Mac

# Install dependencies
pip install -r requirements_kiff.txt
```

### Run Development Server

```bash
# From backend/api directory
cd backend/api
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Access:
- **API**: http://localhost:8000
- **Swagger Docs**: http://localhost:8000/docs
- **OpenAPI Schema**: http://localhost:8000/openapi.json

## API Endpoints

### v1 Endpoints

- `GET /api/v1/health` - Health check
- `GET /api/v1/status` - System status (LLM, Qdrant, MCP)
- `POST /api/v1/chat/messages` - Chat with LLM (supports @tag context injection)
- `GET /api/v1/config/current` - Get current configuration
- `GET /api/v1/config/profiles` - List available profiles
- `GET/POST /api/v1/documents` - Document management
- `POST /api/v1/rag/index` - Build RAG index
- `POST /api/v1/rag/query` - Query with RAG
- `GET /api/v1/mcp/context-sets` - List MCP context sets
- `GET /api/v1/mcp/cache/stats` - Get MCP cache statistics
- `DELETE /api/v1/mcp/cache` - Clear MCP cache

## Docker

```bash
# Build image
docker build -t kiff-ai-backend .

# Run container
docker run -p 8000:8000 kiff-ai-backend
```

## Usage as Git Submodule

This repository is designed to be used as a Git submodule:

```bash
# In deployment repo
git submodule add https://github.com/YOUR_USERNAME/kiff-ai-backend.git backend
git submodule update --init --recursive
```

## Environment Variables

- `QDRANT_URL` - Qdrant server URL (default: http://localhost:6333)
- `LLM_SERVER_URL` - llama.cpp server URL
- `MCP_SERVER_URL` - MCP server URL

## License

Private project
