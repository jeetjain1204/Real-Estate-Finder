# Streamlit Community Cloud — deploy checklist

Follow these steps in your browser. This repo is already structured for Cloud (`requirements.txt` at repo root, entrypoint `streamlit_app.py`, `.streamlit/config.toml`).

## 1. Push to GitHub

Ensure `main` contains:

- `streamlit_app.py`
- `requirements.txt`
- `realestate_finder/` package

## 2. Create the app

1. Open **[share.streamlit.io](https://share.streamlit.io)** and sign in with **GitHub**.
2. Allow Streamlit (Snowflake) **read access** to the repo if GitHub prompts you.
3. Click **Create app** → **Yup, I have an app**.
4. Fill in:
   - **Repository**: `your-name/your-repo`
   - **Branch**: `main` (or your default branch)
   - **Main file path**: `streamlit_app.py`  
   - Optionally set a **custom subdomain** under **App URL**.

## 3. Advanced settings

Click **Advanced settings**:

1. **Python version**: use **3.12** (default) or **3.11** to match local dev.
2. **Secrets**: paste the full contents of **`.streamlit/secrets.toml.example`**, then replace placeholders with real values (see below).
3. Click **Save**, then deploy / reboot the app.

Secrets must use **flat** keys (same as `os.environ`), because `graph.py` maps `st.secrets` into the environment.

### Minimum useful secrets

| Secret | Required? | Purpose |
|--------|-----------|---------|
| `GOOGLE_API_KEY` | Strongly recommended | Gemini parses feedback into preference weights; without it, feedback saves but learning shows an error. |
| `POSTGRES_CONNECTION_STRING` **or** `DATABASE_URL` | Recommended | Persistent buyer memory across reboots (`PostgresSaver`). Same connection string format Neon gives you. |

### Without Postgres (quick try only)

Buyer state lives in SQLite and **resets when the app restarts**. Add:

```toml
REALESTATE_CHECKPOINT_DB = "/tmp/checkpoints.sqlite"
```

### Optional tracing

```toml
LANGSMITH_API_KEY = "..."
LANGSMITH_TRACING_V2 = "true"
LANGSMITH_PROJECT = "realestate-finder"
```

Full template with comments: **`.streamlit/secrets.toml.example`**.

## 4. After deploy

- Open **Manage app → Logs** if the build fails (permissions, missing deps, secrets typos).
- In the UI sidebar **Checkpoint** section, you should see **POSTGRESQL** when Postgres secrets are active.

## 5. Neon Postgres (if you use Cloud persistence)

1. **[neon.tech](https://neon.tech)** → new project → copy **connection string** with `sslmode=require`.
2. Put it in Secrets as `POSTGRES_CONNECTION_STRING` (or `DATABASE_URL`).

Official docs: [Deploy your app](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy), [Secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management).
