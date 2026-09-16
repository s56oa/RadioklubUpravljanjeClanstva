# CLAUDE.md – Radio klub Upravljanje Članstva

Spletna aplikacija za upravljanje članstva radijskega kluba.
Trenutna različica: **v1.29** (produkcijsko stabilna)

## Lokalni zagon

```bash
pip3 install -r requirements.txt
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Testi

```bash
python3 -m pytest tests/ -v
# Pričakovano: 205 testov, 0 napak
```

## Arhitektura

- **Backend:** FastAPI + Jinja2 (SSR), Python 3.12
- **Baza:** SQLite (`data/clanstvo.db`), SQLAlchemy ORM, Alembic migracije
- **Frontend:** Bootstrap 5.3 + DataTables + Bootstrap Icons (CDN), Chart.js (dashboard)
- **Auth:** SessionMiddleware + bcrypt + pyotp (TOTP 2FA); `UserValidationMiddleware` vsako zahtevo preveri uporabnika proti bazi
- **CSP:** `SecurityHeadersMiddleware` doda `Content-Security-Policy` z nonce-om; SQLite `PRAGMA foreign_keys=ON` (od v1.29)

Migracije tečejo samodejno ob zagonu prek `_run_migrations()` v lifespan handlerju.

## Ključni vzorci – OBVEZNO upoštevati

### 1. Jinja2 globals pri vsakem novem routerju
```python
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["csrf_token"] = get_csrf_token  # VEDNO!
```

### 2. Return type hints – ne Union
```python
async def handler(...) -> Response:   # pravilno
async def handler(...) -> Response | RedirectResponse:  # NAPAKA – FastAPIError
```

### 3. Nastavljivi seznami – nikoli hardkodirano
```python
tipi = config.get_tipi_clanstva(db)      # pravilno
razredi = config.get_operaterski_razredi(db)  # pravilno
tipi = ["Osebni", "Mladi", ...]          # NAPAKA
```

### 4. Alembic – nova tabela
Nova tabela → nova migration datoteka v `alembic/versions/`. `Base.metadata.create_all` se ne kliče ročno.

### 5. CSRF na vseh POST endpointih
```python
@router.post("/pot")
async def handler(..., _=Depends(csrf_protect)):
```
V templatu: `{{ csrf_token(request) }}`

### 6. Inline JavaScript – CSP nonce, brez on*="" atributov
```html
<script nonce="{{ request.state.csp_nonce }}">…</script>      <!-- pravilno -->
<form data-confirm="Izbriši {{ x }}?">                          <!-- pravilno: globalni handler v base.html -->
<form onsubmit="return confirm('Izbriši {{ x }}?')">            <!-- NAPAKA: CSP blokira + XSS v JS kontekstu -->
```
Vsi CDN `<script>`/`<link>` morajo imeti `integrity="sha384-…" crossorigin="anonymous"`.

### 7. Session flash (enkratni prikaz)
```python
request.session["kljuc"] = vrednost          # POST handler
vrednost = request.session.pop("kljuc", None) # GET handler
```

## Znani technical debt

*(ni odprtih)*

## Varnost

- Pred zagonom nastavi `SECRET_KEY` in `ADMIN_GESLO` v `.env` – v `OKOLJE=produkcija` se aplikacija s privzetimi vrednostmi NE zažene
- Pregled ranljivosti: `Varnost.md`
- HTTPS se nastavi na reverse proxy-u (Synology / Nginx) – kode ni treba spreminjati

## Deploy

```bash
docker compose up -d   # Uporablja ghcr.io/s56oa/radioklubupravljanjeclanstva:latest
```

CI/CD: GitHub Actions gradi linux/amd64 + linux/arm64 ob push na `main` ali git tagu `vX.Y.Z`.
Git tagi MORAJO biti semver z patch verzijo: `v1.20.0` (ne `v1.20`).

## Dokumentacija

| Datoteka | Vsebina |
|---|---|
| `Izboljsave.md` | Implementirane funkcije + backlog |
| `Varnost.md` | Varnostni pregled, odprte ranljivosti |
| `Uporabniski-prirocnik.md` | Navodila za uporabnike |
| `Tehnicna-dokumentacija.md` | Namestitev, arhitektura, API |
