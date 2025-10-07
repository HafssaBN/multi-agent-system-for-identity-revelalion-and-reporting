import os
import uuid
import time
import asyncio
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Optional, Any

# Make sure to import your compiled LangGraph app
from osint_agent import enhanced_app

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Pydantic Models for OpenAI Compatibility ---

class ModelCard(BaseModel):
    id: str
    object: str = "model"
    created: int = Field(default_factory=lambda: int(time.time()))
    owned_by: str = "owner"

class ModelList(BaseModel):
    object: str = "list"
    data: List[ModelCard]

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    # Allow extra fields to be ignored (this fixes the Bad Request error)
    model_config = ConfigDict(extra="ignore")
    
    model: str
    messages: List[ChatMessage]
    stream: Optional[bool] = False
    # Add common OpenAI parameters that might be sent
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    stop: Optional[List[str]] = None

class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

class ChatCompletionResponseChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str = "stop"

class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[ChatCompletionResponseChoice]
    usage: Usage = Field(default_factory=Usage)

# --- FastAPI Application ---

app = FastAPI(
    title="LangGraph Agent API",
    description="An OpenAI-compatible API for a custom LangGraph OSINT agent.",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests for debugging"""
    start_time = time.time()
    
    # Log request details
    logger.info(f"Incoming request: {request.method} {request.url}")
    logger.info(f"Headers: {dict(request.headers)}")
    
    # For POST requests, log the body (be careful with large payloads)
    if request.method == "POST":
        try:
            body = await request.body()
            logger.info(f"Request body: {body.decode('utf-8')[:500]}...")  # First 500 chars
            # Reset the body stream so it can be read again
            request._body = body
        except Exception as e:
            logger.error(f"Error reading request body: {e}")
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    logger.info(f"Response status: {response.status_code}, Process time: {process_time:.2f}s")
    
    return response

@app.get("/v1/models", response_model=ModelList)
async def list_models():
    """Tells Open WebUI that our 'osint-agent' model is available."""
    logger.info("Models endpoint called")
    return ModelList(data=[ModelCard(id="osint-agent")])

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": int(time.time())}

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """The main endpoint that Open WebUI will call."""
    try:
        # Get raw request body first
        raw_body = await request.body()
        logger.info(f"Raw request body: {raw_body.decode('utf-8')}")
        
        # Parse JSON manually to handle any parsing issues
        import json
        try:
            request_data = json.loads(raw_body.decode('utf-8'))
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON in request body")
        
        logger.info(f"Parsed request data: {request_data}")
        
        # Validate required fields manually
        if "model" not in request_data:
            raise HTTPException(status_code=400, detail="Missing 'model' field")
        
        if "messages" not in request_data or not isinstance(request_data["messages"], list):
            raise HTTPException(status_code=400, detail="Missing or invalid 'messages' field")
        
        # Create the Pydantic model
        try:
            chat_request = ChatCompletionRequest(**request_data)
        except Exception as e:
            logger.error(f"Pydantic validation error: {e}")
            raise HTTPException(status_code=400, detail=f"Request validation error: {str(e)}")
        
        # Check for streaming (not supported yet)
        if chat_request.stream:
             logger.info("Client requested streaming; falling back to non-streaming response.")
        
        # Extract user query from messages
        user_query = ""
        for message in chat_request.messages:
            if message.role == "user":
                user_query = message.content
                break
        
        if not user_query:
            raise HTTPException(status_code=400, detail="No user message found.")
        
        logger.info(f"Received query for agent: {user_query}")
        
        # Prepare initial state for the agent
        initial_state = {
            "original_query": user_query,
            "plan": None,
            "past_steps": [],
            "aggregated_results": {},
            "final_report": "",
            "messages": [],
            "last_step_result": None,
            "last_step_message": None,
            "awaiting_user_confirmation": False,
            "candidate_options": [],
            "selected_candidate": None,
            "current_step": 0,
            "max_steps": 6,
            "executed_tasks": [],
            "failed_approaches": []
        }
        
        logger.info("Invoking the LangGraph agent...")
        
        # Run the agent with error handling
        try:
            final_state = await enhanced_app.ainvoke(
                initial_state, 
                config={"recursion_limit": 30}
            )
            logger.info("Agent run completed successfully.")
        except Exception as agent_error:
            logger.error(f"Agent execution error: {agent_error}")
            # Return a helpful error message instead of crashing
            final_report = f"I encountered an error while processing your request: {str(agent_error)}. Please try rephrasing your query or contact support."
            final_state = {"final_report": final_report}
        
        # Extract the final report
        final_report = final_state.get("final_report", "Error: Could not retrieve the final report.")
        
        # Ensure we have some content
        if not final_report or final_report.strip() == "":
            final_report = "I was unable to generate a response. Please try again with a different query."
        
        # Create the response
        response = ChatCompletionResponse(
            model=chat_request.model,
            choices=[
                ChatCompletionResponseChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=final_report)
                )
            ],
            usage=Usage(
                prompt_tokens=len(user_query.split()),  # Rough estimate
                completion_tokens=len(final_report.split()),  # Rough estimate
                total_tokens=len(user_query.split()) + len(final_report.split())
            )
        )
        
        logger.info("Response created successfully")
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error in chat_completions: {e}")
        logger.exception("Full exception traceback:")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for debugging"""
    logger.error(f"Global exception handler caught: {exc}")
    logger.exception("Full exception traceback:")
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )

# Alternative endpoint for direct testing
@app.post("/api/agent-query")
async def agent_query(request: Request):
    """Direct endpoint for testing the agent without OpenAI compatibility"""
    try:
        body = await request.json()
        user_query = body.get("query")
        
        if not user_query:
            raise HTTPException(status_code=400, detail="Missing 'query' field")
        
        logger.info(f"Direct query received: {user_query}")
        
        initial_state = {
            "original_query": user_query,
            "plan": None,
            "past_steps": [],
            "aggregated_results": {},
            "final_report": "",
            "messages": [],
            "last_step_result": None,
            "last_step_message": None,
            "awaiting_user_confirmation": False,
            "candidate_options": [],
            "selected_candidate": None,
            "current_step": 0,
            "max_steps": 6,
            "executed_tasks": [],
            "failed_approaches": []
        }
        
        final_state = await enhanced_app.ainvoke(
            initial_state, 
            config={"recursion_limit": 30}
        )
        
        return final_state
        
    except Exception as e:
        logger.error(f"Error in agent_query: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Enable more verbose logging for debugging
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8008,
        log_level="debug",
        reload=True
    )