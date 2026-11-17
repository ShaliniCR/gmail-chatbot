# TrainerCentral Assignment Chatbot

A full-stack AI-powered dashboard assistant that connects to the TrainerCentral Assignment Submissions API and answers questions using Anthropic Claude.

---

## 🏗️ Architecture

- **Backend**: FastAPI (Python 3.11+)
  - `/api/chat`: Accepts conversation messages, fetches live learner/submission data from TrainerCentral API, feeds the context to Claude, and streams/returns the response.
  - `/api/health`: Health check endpoint for monitoring and Render zero-downtime deploys.
  - Serves the compiled React frontend static files directly in production.
- **Frontend**: React + Vite SPA
  - Clean, modern chat UI with real-time feedback and responsive layout.
  - Dynamically points to `/api/chat` or a remote API URL via `VITE_API_BASE_URL`.

---

## 🚀 Deployment on Render (render.com)

This project is pre-configured for **1-click / Blueprint deployment on Render**, and can also be deployed as a Docker container or Python Web Service.

### Prerequisites

1. A [Render account](https://render.com).
2. A GitHub or GitLab repository containing this code.
3. Your **Anthropic API key** (`sk-ant-...`).

---

### Option 1: Automatic Blueprint Deploy (Recommended)

Render Blueprints read `render.yaml` and configure everything automatically:

1. Push this repository to **GitHub** or **GitLab**:
   ```bash
   git init
   git add .
   git commit -m "Initial commit for Render deployment"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<your-repo-name>.git
   git push -u origin main
   ```
2. In your [Render Dashboard](https://dashboard.render.com), click **New +** > **Blueprint**.
3. Connect your repository.
4. Render will parse `render.yaml`:
   - Name: `trainer-central-chatbot`
   - Runtime: `python`
   - Build Command: `./build.sh`
   - Start Command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
5. When prompted for environment variables:
   - `ANTHROPIC_API_KEY`: Paste your Anthropic API key.
   - `TRAINER_API_KEY`: (Optional) Your TrainerCentral API key if needed.
6. Click **Apply**. Render will install dependencies, build the React frontend, launch FastAPI, and provide your public URL (e.g. `https://trainer-central-chatbot.onrender.com`).

---

### Option 2: Manual Web Service Setup on Render

If you prefer to configure the service manually in the Render dashboard:

1. In Render Dashboard, click **New +** > **Web Service**.
2. Select your repository.
3. Configure the settings:
   - **Name**: `trainer-central-chatbot`
   - **Language**: `Python 3`
   - **Region**: Any (e.g., Oregon)
   - **Branch**: `main`
   - **Build Command**: `./build.sh`
   - **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   - **Plan**: `Free`
4. Expand **Advanced** > **Environment Variables** and add:
   - `PYTHON_VERSION` = `3.11.9`
   - `ANTHROPIC_API_KEY` = `<your-anthropic-api-key>`
   - `ANTHROPIC_MODEL` = `claude-opus-5-5`
   - `TRAINER_API_KEY` = `<optional-trainer-key>`
5. Expand **Advanced** > **Health Check Path** and set:
   - `/api/health`
6. Click **Create Web Service**.

---

### Option 3: Deploy with Docker on Render

A multi-stage `Dockerfile` is included:

1. In Render Dashboard, click **New +** > **Web Service**.
2. Connect your repository.
3. Choose **Docker** as the runtime.
4. Set the environment variables (`ANTHROPIC_API_KEY`, etc.).
5. Click **Create Web Service**.

---

## 💻 Local Development

### 1. Setup Backend
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Create .env from template
cp .env.example .env
# Edit .env with your keys

# Run FastAPI backend
uvicorn backend.main:app --reload --port 8000
```

### 2. Setup Frontend
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser. Vite automatically proxies `/api` requests to `http://localhost:8000`.

---

## ⚙️ Environment Variables Reference

| Variable | Description | Required | Default |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Anthropic Claude API Key | Yes (for chat) | - |
| `ANTHROPIC_MODEL` | Claude model name | No | `claude-opus-5-5` |
| `TRAINER_API_KEY` | Sent as `x-api-key` to TrainerCentral API | No | - |
| `DASHBOARD_API_BASE` | Base URL for the TrainerCentral submissions API | No | `https://trainer-central-assigments-api.onrender.com` |
| `PORT` | Web server port (injected automatically by Render) | No | `8000` |
| `VITE_API_BASE_URL` | Used if frontend is deployed separately | No | `""` (relative `/api`) |
