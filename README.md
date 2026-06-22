# ShopBuddy: Agentic E-Commerce Assistant

ShopBuddy is an intelligent, agentic E-Commerce Assistant built with LangGraph, FastAPI, and Model Context Protocol (MCP). It helps users find product prices, read reviews, and get buying guidance using a combination of local Astra DB vector search and DuckDuckGo web search fallbacks.

## Features
- **Agentic Routing:** Uses LangGraph to intelligently route conversational queries versus product queries.
- **RAG with Astra DB:** Connects to Datastax Astra DB for local, low-latency product retrieval using Sentence Transformers embeddings.
- **MCP Tool Integration:** Leverages the Model Context Protocol to decouple search logic (both local and web) into dedicated subprocess servers.
- **Self-Reflective Grader:** An LLM grader evaluates retrieved local documents. If local documents aren't relevant, the query is rewritten and passed to a web search fallback.
- **FastAPI Backend:** Offers a chat-based user interface and REST endpoints.

## Architecture
- **LangGraph:** Orchestrates the flow (`Assistant -> Retriever -> Grader -> Generator / Rewriter -> Web Search`).
- **FastAPI:** Serves the frontend (`/`) and handles message generation (`/get`).
- **MCP Server (`stdio`):** Runs the search and retrieval tools as isolated components for security and scalability.
- **Groq Llama / GPT-OSS:** Powers the underlying LLMs for fast inference.

## Getting Started

### Prerequisites
- Python 3.10+
- Astra DB Account
- Groq API Key

### Installation

1. Clone the repository and navigate to the project directory.
2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your `.env` file based on `.env.example`:
```env
GROQ_API_KEY=your_groq_api_key
OPENAI_API_KEY=your_openai_api_key
GOOGLE_API_KEY=your_google_api_key
ASTRA_DB_API_ENDPOINT=your_astra_db_endpoint
ASTRA_DB_APPLICATION_TOKEN=your_astra_db_token
ASTRA_DB_KEYSPACE="default_keyspace"
```

### Running the Application

Start the FastAPI application:
```bash
python -m uvicorn prod_assistant.router.main:app --host 0.0.0.0 --port 8001
```

Once running, open your browser and navigate to:
**http://localhost:8001/** to access the Chat UI.

*(Note: The very first query may take 30-45 seconds as the MCP server cold-starts and downloads the SentenceTransformer weights. Subsequent queries are significantly faster.)*

## Future Optimizations
- **Astra DB Ingestion:** Load real product catalogs into the `ecommercedata` collection.
- **Prompt Tuning:** Refine the rewriter prompt to ensure DuckDuckGo searches do not hallucinate on abstract queries.
- **Logging Fixes:** Convert stdout prints in the MCP tools to proper stderr logging to improve MCP JSON-RPC protocol stability.
