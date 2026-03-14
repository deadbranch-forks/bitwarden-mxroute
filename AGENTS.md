# Repository Guidelines

## Project Structure & Module Organization
- `server/`: Starlette API that mimics the Addy.io endpoints and talks to MXRoute. Core entrypoint is `server/app.py`; tests live in `server/test_app.py`.
- `web/`: Vite + React + Tailwind front end. Entry point `web/src/main.tsx`, UI in `web/src/components/` and `web/src/App.tsx`.
- `docker-compose*.yml`: Container orchestration for dev/prod or prebuilt images.
- `.env.example`: Required environment variables template.

## Build, Test, and Development Commands
- `docker-compose up -d`: Run the published images locally (uses `.env.example`).
- `docker-compose -f docker-compose.dev.yml up --build`: Build and run dev images from source.
- `docker-compose -f docker-compose.prod.yml up --build`: Build and run production images from source.
- `cd server && uvicorn app:app --host 0.0.0.0 --port 6123 --reload`: Run the API locally with hot reload.
- `cd web && npm install && npm run dev`: Run the web app with Vite.
- `cd web && npm run build`: Typecheck and build the web app.
- `cd web && npm run lint`: Run ESLint.

## Coding Style & Naming Conventions
- Python: 4-space indentation, snake_case for functions/variables, and keep endpoints in `server/app.py` concise.
- TypeScript/React: 2-space indentation, semicolons, double quotes, PascalCase components (`ForwarderItem.tsx`), and camelCase hooks/utilities.
- Use ESLint for web code. No formatter is enforced in this repo; match surrounding style.

## Testing Guidelines
- Server tests use `pytest` in `server/test_app.py`.
- Run: `cd server && pytest` (install `pytest` in your venv if needed).
- No dedicated frontend test runner is configured; add tests if you introduce complex UI logic.

## Commit & Pull Request Guidelines
- Commits follow Conventional Commits seen in history: `feat:`, `fix:`, `chore:` (optionally add a scope like `feat(web): ...`).
- PRs should include a short summary, testing steps, and linked issues. Add screenshots or screen recordings for UI changes.

## Security & Configuration Tips
- Never commit real credentials. Use `.env.example` as the reference and keep secrets in local `.env.*` files.
- The API requires `SERVER_API_TOKEN` and MXRoute credentials to function; document any new env vars in `README.md`.
