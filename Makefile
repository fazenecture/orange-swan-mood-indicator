dev:
	uv run dev

start:
	uv run start

lint:
	uv run ruff check .

format:
	uv run ruff format .

deploy:
	git pull
	uv sync
	pm2 restart mood_analyzer