# 🛡️ GuardAI — Advanced Reddit Content Moderation System

GuardAI is a production-grade machine learning system designed to automatically analyze, classify, and moderate social media content (specifically Reddit). Using a **DistilBERT** neural network fine-tuned on tens of thousands of labelled social media posts, this system acts as an automated moderator that detects hate speech and toxic behavior in real-time.

It features a full React dashboard, a RESTful API built in Flask, PostgreSQL for data persistence, and an **Active Feedback Loop** that allows the AI to learn and improve from human corrections.

> **Tech Stack**: Python (Flask) · React (Vite) · PostgreSQL · HuggingFace Transformers (DistilBERT) · Docker

---

## 🏛️ System Architecture

```text
┌─────────────────┐       REST API         ┌──────────────────┐
│  React (Vite)   │ ─────────────────────▶ │   Flask (5000)   │
│  Port 3000      │ ◀───────────────────── │                  │
└─────────────────┘                        │  ┌────────────┐  │
        │                                  │  │ DistilBERT │  │
        │                                  │  └────────────┘  │
        │                                  │         │        │
        │                                  │  ┌──────▼─────┐  │
        └──────── (Active Learning) ───────┼─▶│ PostgreSQL │  │
                                           │  └──────┬─────┘  │
                                           └─────────┼────────┘
                                                     │
                                           ┌─────────▼─────────┐
                                           │   CSV / Reddit    │
                                           └───────────────────┘
```

## ✨ Key Features
- **Live Content Analysis**: Analyze subreddits to get a breakdown of hate speech vs. safe content.
- **Deep Learning Accuracy**: Uses DistilBERT, providing robust contextual understanding way beyond keyword-matching.
- **Severity Scoring & Toxic Highlights**: Precise visual feedback on *why* a post was flagged.
- **Data Flywheel (Active Learning)**: Users can click 👍 or 👎 on predictions. The system logs corrections to a database, allowing scheduled retraining scripts to continuously improve the model without human intervention.
- **Production-Ready Endpoints**: Fully validated REST API with error handling.

---

## 🚀 Step-by-Step Setup Guide

Follow these commands to get the entire project running locally.

### Step 1: Clone and Configure Environment
First, clone the code and create your environment variables file.
```bash
# 1. Copy the example environment template
cp .env.example .env

# Optional: Open .env in a text editor and add the DATABASE_URL. 
# Defaults to: postgresql://moderator:password@localhost:5432/content_moderation
```

### Step 2: Start the Database (Docker)
We use Docker to instantly spin up a PostgreSQL instance without complex local installations.
```bash
# Start the database in detached mode
docker-compose up -d db
```

### Step 3: Setup the Python Backend
Install the backend dependencies and initialize the database schema.
```bash
# 1. Navigate to the backend directory
cd backend

# 2. Create a virtual environment (Optional but highly recommended)
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate

# 3. Install required Python packages
pip install -r requirements.txt

# 4. Initialize the PostgreSQL Database schema and load offline data
python -m db.init_db
```

### Step 4: Train the DistilBERT Model
The system needs to train the core intelligence engine. This takes about **20 minutes** on a standard CPU.
```bash
# Still inside the 'backend' folder:
python -m ml.train
```

### Step 5: Start the Flask API Server
Once training completes safely, turn on the API so the frontend can talk to it.
```bash
# Run the Flask API on port 5000
flask --app api.main run --port 5000
```
> Let this terminal run. Open a **new terminal window** for Step 6.

### Step 6: Start the React Frontend
```bash
# 1. Open a new terminal and navigate to the frontend
cd frontend

# 2. Install Node.js packages
npm install

# 3. Start the Vite development server
npm run dev
```

**🎉 Success!** You can now open your browser to `http://localhost:5173` (or whatever port Vite gives you) to access the Dashboard.

---

## 🔁 How the Active Feedback Loop Works

Because language (slang, code words) constantly evolves, an AI model will degrade over time if left static.

1. **Submit Feedback**: On the React interface, clicking 👍 or 👎 triggers `POST /feedback`.
2. **Store Correction**: Flask saves the explicit correction securely into the `user_feedback` PostgreSQL table.
3. **Retrain Model**: Periodically, you can run the background script:
   ```bash
   python -m ml.retrain
   ```
   This script gathers all mismatched feedback and automatically *fine-tunes* DistilBERT on the new examples, making the model permanently smarter against edge cases.

---

## 🧪 Running Tests
To verify the complex API logic and ensure nothing is broken:
```bash
cd backend
pytest tests/ -v
```

## 📖 API Reference
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Server health-check |
| `POST` | `/predict` | Single text manual classification |
| `GET` | `/analyze/reddit` | Full subreddit automated batch analysis |
| `POST` | `/feedback` | Active learning feedback loop |
| `GET` | `/analytics` | System-wide performance stats |
