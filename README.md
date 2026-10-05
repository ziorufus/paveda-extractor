# PaVeDa Excel Manager

Web interface to upload, version and convert the PaVeDa (ValPaL) Excel annotation files.

- `backend/`: FastAPI + SQLAlchemy (SQLite by default). Reuses `scripts/converter_core.py` for the conversion.
- `frontend/`: Vue 3 + Vite + Bootstrap.

## Google OAuth2

In the Google Cloud Console create an OAuth client ID of type *Web application* and add
`http://localhost:8000/auth/callback` (or your `GOOGLE_REDIRECT_URI`) to the *Authorized redirect URIs*.
Put client ID and secret in `backend/.env`.

## Backend

```bash
cd backend
cp .env.example .env        # then fill in the values
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
```

`config.json` is the essential version of `scripts/config.json`; `$BASE` in string values is replaced with `base_folder`.
`input_folder` (CLDF data), `excel_folder` (where `new_mm_file` is read from) and `alt_classes_folder` are still read from disk.

On first startup (empty `projects` table) the languages and sets in `config.json` are imported, and the Excel files
found in `excel_folder` are stored as version 1 of each language. The first user who logs in becomes the
permanent administrator; afterwards only e-mail addresses added by an administrator can log in.

## Frontend

```bash
cd frontend
cp .env.example .env        # VITE_API_BASE_URL = backend address
npm install
npm run dev                 # http://localhost:5173
```

For production, `npm run build` creates `dist/`: serve it with a fallback to `index.html` (the app uses HTML5 history routing),
and set `FRONTEND_URL` / `GOOGLE_REDIRECT_URI` in `backend/.env` accordingly.
