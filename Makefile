# Makefile

# Run the backend server
backend:
	uvicorn agent_server:app --host 0.0.0.0 --port 8008 --reload --log-level debug

# Run the frontend (Windows command)
frontend:
	cd ".\multi-agent-system-for-identity-revelalion-and-reporting\agent_backend" && open-webui serve

# Run both backend and frontend together
all: backend frontend
