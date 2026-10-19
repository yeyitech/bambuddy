ARG BASE_IMAGE
FROM ${BASE_IMAGE}
COPY backend/app/api/routes/home_ledger.py /app/backend/app/api/routes/home_ledger.py
COPY backend/app/services/home_ledger_store.py /app/backend/app/services/home_ledger_store.py
COPY backend/app/services/home_material_accounting.py /app/backend/app/services/home_material_accounting.py
# Register the isolated extension without replacing upstream main.py.
RUN python -c "from pathlib import Path; p=Path('/app/backend/app/main.py'); s=p.read_text(); marker='# API routes'; assert marker in s; p.write_text(s.replace(marker, 'from backend.app.api.routes import home_ledger\\napp.include_router(home_ledger.router, prefix=app_settings.api_prefix)\\n\\n'+marker, 1))"
COPY static/ /app/static/
