
# 🔍 Multi-Agent System for Identity Revelation and Reporting

This repository contains a lightweight **OSINT-focused multi-agent backend** and a **local Web UI frontend** used for identity investigation, username analysis, and intelligence report generation.  
The system uses an LLM-based agent (`osint_agent.py`) connected to a FastAPI backend (`agent_server.py`) and a WebUI frontend (Open-WebUI).

---

## 🗂️ Repository Structure

```

multi-agent-system-for-identity-revelalion-and-reporting/
│
├── agent_backend/
│   ├── agent_server.py        # FastAPI backend + agent routing
│   ├── osint_agent.py         # OSINT analysis agent logic
│   ├── uvicorn                # Helper script for launching backend
│   ├── .webui_secret_key      # Auto-generated secret for WebUI
│   ├── **init**.py
│
└── agent_frontend/            # served by Open-WebUI

````

---

## 🚀 Overview

This project provides:

- 🧠 **An OSINT Agent** capable of analyzing usernames, traces, and identity clues.  
- 🌐 **FastAPI Backend** to expose agent reasoning and tool calls.  
- 💬 **WebUI Frontend (Open-WebUI)** for interactive conversations with the agent.  
- 🔁 **Real-time tool execution logs** and agent reasoning visibility.  

This architecture enables interactive identity investigation through a clean interface.

---

## 🛠️ Backend Setup

### 1️⃣ Install dependencies (inside `agent_backend/`)

If you have a `requirements.txt`:

```bash
pip install -r requirements.txt
````

Otherwise, install the essentials manually:

```bash
pip install fastapi uvicorn python-dotenv pydantic
```

---

## ▶️ Run the Backend

From inside `agent_backend/`:

```bash
uvicorn agent_server:app --host 0.0.0.0 --port 8008 --reload --log-level debug
```

Backend will start at:
👉 **[http://localhost:8008](http://localhost:8008)**

---

## 🖥️ Run the Frontend (Open-WebUI)

Navigate to your backend folder:

```bash
open-webui serve
```

The frontend will start (usually on port 8080):

👉 **[http://localhost:8080](http://localhost:8080)**

---

## 🔗 Connect Frontend → Backend

In Open-WebUI settings:

1. Go to **Settings → Backend API**
2. Set:

```
http://localhost:8008
```

3. Save and refresh.

You can now chat with your OSINT AI agent.

---

## 🧠 Core Components

### `osint_agent.py`

* Defines the identity-analysis agent
* Implements OSINT logic
* Handles reasoning, queries, and multi-step decision making

### `agent_server.py`

* FastAPI server
* Exposes endpoints
* Routes messages to the OSINT agent
* Handles tool calls and streaming responses

### `uvicorn`

* Shortcut script for launching backend

---

## 📡 API Endpoints

### **POST /message**

Send a message to the OSINT agent.

### **GET /health**

Check backend health.

### **POST /run**

Trigger an OSINT investigation sequence (if implemented).

---

## 📘 Example Usage

Ask the system:

```
Investigate the username 'crypt0_fox' and generate an identity report.(this username should be in the database)
```

Or:

```
Analyze this profile bio and guess potential nationality and domain of expertise.
```

The backend will orchestrate the OSINT agent, run tools, and stream results to the WebUI.

---

## 🤝 Contributing

Feel free to submit issues or pull requests.

---

## 📜 License

MIT License (or your preferred license)

