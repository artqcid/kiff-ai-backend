# KIFF AI Backend

FastAPI Backend for the KIFF LangChain Agent with RAG, MCP integration, and LLM orchestration.

## Features

- 🚀 FastAPI with OpenAPI/Swagger documentation
- 💬 Chat orchestration with llama.cpp integration
- 🔍 RAG (Retrieval-Augmented Generation) with Qdrant
- 🌐 MCP (Model Context Protocol) for web context
- 📁 Document management and processing
- ⚙️ Profile and configuration management

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
│   ├── models.py     # Pydantic models
│   └── v1/           # API v1 endpoints
│       ├── chat.py
│       ├── config.py
│       ├── documents.py
│       ├── health.py
│       ├── mcp.py
│       └── rag.py
├── core/             # Business logic
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
- `POST /api/v1/chat` - Chat with LLM
- `GET /api/v1/config/current` - Get current configuration
- `GET /api/v1/config/profiles` - List available profiles
- `GET/POST /api/v1/documents` - Document management
- `POST /api/v1/rag/index` - Build RAG index
- `POST /api/v1/rag/query` - Query with RAG
- `GET /api/v1/mcp/context` - Get MCP context

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
