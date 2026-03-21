# 🧠 Deep Dive: GuardAI Architecture & Technical Decisions

This document serves as a comprehensive explanation of **GuardAI**, explaining not just *how* the code functions, but *why* specific architectural decisions were made, what alternatives were considered, and how the entire system communicates as a unified entity.

---

## 1. Executive Summary & Purpose

**The Problem**: Social media platforms generate millions of text comments daily. Manual human moderation is mathematically impossible at scale. Simple keyword-blocking (e.g., banning "bad words") is easily circumvented by users and fails to understand context (e.g., "This movie killed it!" vs. "I am going to kill you").

**The Solution**: GuardAI is a full-stack, decoupled architecture utilizing Natural Language Processing (NLP) via deep learning to understand contextual toxicity, combined with an active learning pipeline to guarantee the model stays relevant as internet culture changes.

---

## 2. High-Level Architecture Pattern

The system follows a classic **N-Tier (Decoupled Microservices-lite)** architecture. 
Instead of a monolith where HTML is generated server-side (like Django templates), we fully separated the Presentation layer (React) from the Compute layer (Flask/DistilBERT), communicating strictly over REST JSON APIs.

### Why this architecture?
- **Separation of Concerns**: Frontend engineers can edit the React UI without touching PyTorch neural network logic.
- **Scalability**: Heavy ML workloads require GPU acceleration. By keeping the backend an isolated REST API, we can host the exact same React code on a tiny free server (Vercel) while pushing the Flask code to a high-powered GPU cluster.

---

## 3. The Frontend (React + Vite)
The presentation layer is built in React using Vite as the bundler.

- **How it works:** Users type a subreddit name. React fires an asynchronous `fetch()` request to the Flask server. While waiting, it displays dynamic loading states. Once results arrive, it selectively renders the data into charts, lists, and highlighting modules.
- **UI Mechanism:** It uses plain, vanilla CSS with custom variables (`index.css`) rather than Tailwind or Bootstrap.
- **Alternative Considered:** Next.js. We chose Vite/React because this is a Single Page Application (SPA) heavily reliant on client-side state, and we do not need Server Side Rendering (SSR) SEO benefits for an internal moderation dashboard.

---

## 4. The Backend (Flask + REST API)
Flask acts as the traffic controller. It receives HTTP requests, talks to the database, talks to the Machine Learning model, and formats the output into standard JSON.

- **How it works:** `api/main.py` is the application factory. `api/routes.py` houses endpoints (e.g., `/analyze/reddit`). When `/analyze/reddit` is called, Flask:
  1. Queries the Database via `data/reddit_fetcher.py`.
  2. Batches the text.
  3. Sends the batch to the `ContentModerationModel` for inference.
  4. Takes the resulting predictions and creates records in PostgreSQL.
  5. Serializes the final results back to React.
- **Alternative Considered:** FastAPI. FastAPI is excellent for async python, but for heavy CPU-bound machine learning tasks, async does not inherently speed up matrix multiplications. Flask provides a robust, heavily documented ecosystem perfect for this synchronous ML pipeline.

---

## 5. The Database Layer (PostgreSQL & SQLAlchemy)
All data, analytics, and corrections are permanently stored in PostgreSQL.

- **How it works:** We use **SQLAlchemy ORM**. Instead of writing raw SQL strings (which are prone to SQL injection attacks), we define Python classes (like `Content` and `Prediction` in `db/database.py`).
- **Why PostgreSQL?** SQLite is easier to set up but strictly locks during concurrent database writes. In a system where an AI is writing 500 predictions per second, SQLite will crash with a `Database is locked` error. PostgreSQL gracefully handles high-concurrency writes.

---

## 6. The Machine Learning Engine (DistilBERT)
This is the brain of the operation, structured inside the `backend/ml/` directory.

- **How it works:** We use HuggingFace Transformers. DistilBERT is a "distilled" (smaller, faster) version of BERT (Bidirectional Encoder Representations from Transformers). The script `train.py` loads `Twitter Sentiments.csv`, cleans it, tokenizes the words into numerical arrays, and adjusts the weights of the neural network using backpropagation until it learns to recognize patterns of hate speech.
- **Alternative Considered (Baseline):** Term Frequency-Inverse Document Frequency (TF-IDF) + Logistic Regression. 
  - *Why not stick with TF-IDF?* TF-IDF only counts the *frequency* of words (Bag of Words). "I am not happy" and "Happy I am not" look identical to TF-IDF. DistilBERT uses Attention Mechanisms to read bidirectionally, understanding context perfectly.

---

## 7. The Continuous Learning Pipeline (Data Flywheel)
This is the feature that promotes the app from a "toy" to an "enterprise tier" project.

- **The Problem:** Model Drift. The way toxic users speak in 2026 is different than 2021. If the model is frozen, it becomes obsolete.
- **The Implementation:** 
  1. The UI has 👍 and 👎 buttons for every prediction.
  2. Clicking 👎 fires an API call storing the correction in the `user_feedback` database table.
  3. A specialized script (`ml/retrain.py`) fetches specifically the rows where the original prediction was wrong.
  4. It uses PyTorch to inject those edge-cases directly back into the DistilBERT model, fine-tuning the weights specifically on its mistakes.
- **The Result:** The AI structurally mimics human learning. The more it is used, the smarter it gets.

---

## 8. Summary of Future Steps
If the application needs to scale to 100,000 requests per minute, the architecture must evolve:
1. **Asynchronous Background Queues:** Moving ML inference inside a Celery + Redis worker so pulling large requests doesn't block the main Flask thread.
2. **Caching:** Storing exact API responses in Redis so duplicate searches process in milliseconds without touching the neural network.
