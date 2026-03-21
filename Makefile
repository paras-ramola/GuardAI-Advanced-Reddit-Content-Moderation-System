.PHONY: help install setup-db load-data train serve frontend test lint docker-up docker-down

help:
	@echo ""
	@echo "  GuardAI — Reddit Content Moderation (Offline Mode)"
	@echo "  ===================================================="
	@echo "  make install               Install all dependencies"
	@echo "  make setup-db              Initialize PostgreSQL schema"
	@echo "  make load-data CSV=<path>  Bulk load Reddit CSV into DB"
	@echo "  make load-sample CSV=<p>   Load first 100K rows (test)"
	@echo "  make train                 Train ML model (baseline + DistilBERT)"
	@echo "  make serve                 Start Flask API (port 5001)"
	@echo "  make frontend              Start React dev server (port 3000)"
	@echo "  make test                  Run pytest"
	@echo "  make lint                  Run flake8"
	@echo "  make docker-up             Full stack with Docker Compose"
	@echo "  make docker-down           Stop Docker services"
	@echo ""

install:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

setup-db:
	cd backend && python -m db.init_db

load-data:
	@test -n "$(CSV)" || (echo "❌ Usage: make load-data CSV=/path/to/reddit.csv" && exit 1)
	cd backend && python -m data.load_reddit_csv --csv "$(CSV)"

load-sample:
	@test -n "$(CSV)" || (echo "❌ Usage: make load-sample CSV=/path/to/reddit.csv" && exit 1)
	cd backend && python -m data.load_reddit_csv --csv "$(CSV)" --sample 100000

train:
	cd backend && python -m ml.train

serve:
	cd backend && flask --app api.main run --host=0.0.0.0 --port=5001 --debug

frontend:
	cd frontend && npm run dev

test:
	cd backend && pytest tests/ -v --tb=short

lint:
	cd backend && flake8 . --max-line-length=100 --exclude=ml/artifacts,__pycache__

docker-up:
	docker-compose up --build

docker-down:
	docker-compose down -v
