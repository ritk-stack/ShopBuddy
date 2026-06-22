import uvicorn
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import HumanMessage
from workflow.agentic_workflow_with_mcp_websearch import AgenticRAG
from contextlib import asynccontextmanager

# Global agent reference
rag_agent = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global rag_agent
    rag_agent = AgenticRAG()
    await rag_agent.async_init()
    yield
    # Clean up if necessary
    rag_agent = None

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- FastAPI Endpoints ----------

@app.get("/status")
def status():
    return {
        "status": "LIVE",
        "project": "E-commerce Product Assistant",
        "message": "Backend is running on AWS EKS"
    }

@app.get("/health")
def health():
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})


@app.post("/get")
async def chat(msg: str = Form(...)):
    import uuid
    if not rag_agent:
        return "Assistant is still initializing. Please try again."
    
    thread_id = str(uuid.uuid4())
    answer = await rag_agent.run(msg, thread_id=thread_id)
    return answer