# Multi-tenant arhitektura – Evaluacija

*Dokument: evaluacija možnosti za multi-tenant verzijo aplikacije Radio klub Člani*
*Datum: 2026-02-24 | Status: evaluacija, ni obveza implementacije*

---

## Kontekst in zahteve

ZRS (Zveza radioamaterjev Slovenije) bi gostila centralno instanco za 20–100 radioklubov na Linux x64 strežniku.

**Potrjene zahteve:**
- 20–100 tenantov (radioklubov)
- Brez cross-tenant poizvedb – klubi so popolnoma neodvisni
- Podatkovna izolacija je **kritična** (GDPR)
- Portabilnost je zaželena: klub mora moći vzeti svoje podatke in zagnati lastno standalone instanco
- Super-admin tier: samo kreiranje tenantov in admin računov, brez dostopa do podatkov

---

## Kazalo

1. [Arhitekturne variante](#1-arhitekturne-variante)
2. [Primerjalna tabela](#2-primerjalna-tabela)
3. [Priporočena arhitektura (Option B)](#3-priporočena-arhitektura-option-b)
4. [Alternativa za večjo skalo (Option C)](#4-alternativa-za-večjo-skalo-option-c)
5. [Super-admin tier](#5-super-admin-tier)
6. [URL in routing strategija](#6-url-in-routing-strategija)
7. [Ocena dela po opcijah](#7-ocena-dela-po-opcijah)
8. [Varnost in GDPR](#8-varnost-in-gdpr)
9. [Docker in infrastruktura](#9-docker-in-infrastruktura)
10. [Portabilnost – exit strategija](#10-portabilnost--exit-strategija)
11. [Tveganja in odprtа vprašanja](#11-tveganja-in-odprta-vprašanja)

---

## 1. Arhitekturne variante

### Option A – Več Docker instanc (ena per klub)

Vsak radioklub dobi ločen Docker vsebnik z lastno instanco aplikacije.

```
nginx
├── s59dgo.clanstvo.zrs.si  →  container radioklub-s59dgo  (port 8001)
├── s59abc.clanstvo.zrs.si  →  container radioklub-s59abc  (port 8002)
└── s59xyz.clanstvo.zrs.si  →  container radioklub-s59xyz  (port 8003)
```

**Prednosti:**
- Nič kode ni treba spremeniti – obstoječa aplikacija deluje brez modifikacij
- Popolna izolacija na ravni procesa, OS in datotečnega sistema
- En klub ne more vplivati na delovanje drugega (memory leak, crashed process, itd.)
- Posodobitev enega kluba ne vpliva na druge
- Portabilnost je trivialna – vsak klub ima svojo `./data/clanstvo.db`

**Slabosti:**
- Operativno breme: 50 klubov = 50 vsebnikov, 50 `.env` datotek, 50 nginx location blokov
- Poraba RAM: ~50–100 MB per instanca × 50 = 2.5–5 GB samo za aplikacije
- Ni centralnega super-admin vmesnika – vse se konfigurira ročno ali s skripti
- Posodobitev kode zahteva rebuild vseh vsebnikov

**Ocena dela:** 1–3 dni (samo infrastruktura, brez kode)

---

### Option B – Ena instanca, ločena SQLite baza per tenant ✅ Priporočeno

Ena aplikacija, vsak klub ima svojo `data/<tenant_id>/clanstvo.db`. Tenant se identificira iz subdomene ali URL poti.

```
nginx (wildcard subdomain)
    │
    ▼
FastAPI (ena instanca, port 8000)
    │
    ├── TenantMiddleware  →  prebere subdomain → tenant_id
    │
    ├── DynamicDBMiddleware  →  odpre/cachira SQLiteEngine za tenant
    │
    ├── request.state.tenant_id = "s59dgo"
    ├── request.state.db = Session(s59dgo_engine)
    │
    data/
    ├── s59dgo/clanstvo.db
    ├── s59abc/clanstvo.db
    └── s59xyz/clanstvo.db
```

**Prednosti:**
- Popolna GDPR izolacija: vsaka baza je fizično ločena datoteka
- Portabilnost: klub vzame svojo `.db` in zažene standalone instanco brez sprememb
- Ena aplikacija = en proces, en Docker vsebnik, ena posodobitev kode
- Obstoječa arhitektura (SQLAlchemy, Jinja2, SQLite) se ne zamenja
- Backup per tenant je preprost (`cp data/s59dgo/clanstvo.db ...`)

**Slabosti:**
- Zmerna količina kode: tenant middleware, dynamic DB routing, super-admin UI
- SQLite connection pool pri 50+ sočasnih tenantih zahteva premišljeno upravljanje
- SQLite WAL mode priporočen za boljšo sočasnost
- Nič cross-tenant poizvedb (kar je v tem primeru zahteva, ne slabost)

**Ocena dela:** 6–10 tednov

---

### Option C – Ena instanca, PostgreSQL s shemami per tenant

Ena PostgreSQL baza, vsak tenant dobi svojo shemo (`s59dgo.*`, `s59abc.*`).

```
FastAPI
    │
    ├── TenantMiddleware  →  set search_path = s59dgo
    │
PostgreSQL
    ├── schema: s59dgo  →  clani, clanarine, aktivnosti, ...
    ├── schema: s59abc  →  clani, clanarine, aktivnosti, ...
    └── schema: super_admin  →  tenanti, super_admin_log
```

**Prednosti:**
- Industrijski standard za multi-tenancy pri tej skali
- Izolacija na ravni DB sheme – PostgreSQL to nativno podpira
- Boljša sočasnost kot SQLite pri večjem prometu
- Backup per tenant z `pg_dump --schema=s59dgo`
- Potencial za kasnejše cross-tenant poizvedbe če bi bila potrebna

**Slabosti:**
- **Velik odmik od obstoječe arhitekture**: SQLite → PostgreSQL migracija je obsežna
- Potreben Alembic ali lastna migracijska logika per shemo
- Portabilnost je slabša: klub ne more "vzeti" PostgreSQL sheme in zagnati standalone SQLite instanco brez konverzijskega koraka
- Kompleksnejša lokalna razvojna okolja
- Operativni overhead: PostgreSQL vzdrževanje, backup, replication

**Ocena dela:** 12–18 tednov

---

### Option D – Ena baza, shared tabele z `tenant_id` stolpcem

Vsi klubi v isti bazi, vsaka tabela dobi `tenant_id` kolono.

```sql
CREATE TABLE clani (
    id INTEGER PRIMARY KEY,
    tenant_id TEXT NOT NULL,  -- ← dodan
    priimek TEXT, ime TEXT, ...
);
```

**Prednosti:**
- Najmanj infrastrukturnih sprememb
- Enostavna implementacija

**Slabosti:**
- **Kritično za GDPR: funkcionalna izolacija brez fizične ločenosti**
- Vsak bug v query-ju (pozabljen WHERE tenant_id = ?) razkrije podatke drugega kluba
- Backup enega kluba zahteva filtriranje iz skupne baze
- Portabilnost zahteva kompleksen izvoz
- **Ni primerno za to aplikacijo glede na zahtevo po kritični izolaciji**

**Priporočilo: izključiti Option D.**

---

## 2. Primerjalna tabela

| Kriterij | Option A (več instanc) | Option B (ena instanca, ločene SQLite) | Option C (PostgreSQL sheme) | Option D (shared tabele) |
|----------|------------------------|----------------------------------------|----------------------------|--------------------------|
| **GDPR izolacija** | ✅ Fizična (OS level) | ✅ Fizična (datoteka) | ✅ Fizična (shema) | ⚠️ Samo logična |
| **Portabilnost** | ✅ Trivialna | ✅ Odlična | ⚠️ Zahteva konverzijo | ❌ Kompleksna |
| **Kode za spremeniti** | ✅ Nič | ⚠️ Zmerno (~1500–2500 vrstic novih) | ❌ Obsežno (migracija DB) | ⚠️ Srednje |
| **Ops pri 50 klubih** | ❌ 50 vsebnikov | ✅ 1 vsebnik | ✅ 1 vsebnik + PostgreSQL | ✅ 1 vsebnik |
| **RAM poraba** | ❌ ~3–5 GB | ✅ ~200–400 MB | ✅ ~200–400 MB + PG | ✅ nizka |
| **Backup per tenant** | ✅ Trivialen | ✅ Preprost | ⚠️ pg_dump --schema | ❌ Kompleksen |
| **Sočasnost** | ✅ Ločeni procesi | ⚠️ SQLite WAL mode | ✅ PostgreSQL native | ✅ PostgreSQL |
| **Obseg dela** | 1–3 dni | 6–10 tednov | 12–18 tednov | 6–10 tednov |
| **Priporočilo** | Za hiter start | **Optimalno** | Za 100+ klubov | Izključiti |

---

## 3. Priporočena arhitektura (Option B)

### Zakaj Option B?

Glede na zahteve (20–100 klubov, GDPR kritično, portabilnost zaželena, brez cross-tenant poizvedb) je Option B optimalna izbira:

- Ohranja vse prednosti obstoječe arhitekture (SQLite, SQLAlchemy, Jinja2)
- Fizična izolacija baz zadosti GDPR zahtevam
- Portabilnost je inherentna – klub vzame `.db` datoteko
- Ena instanca = enostavno vzdrževanje in posodobitve
- Obseg dela je realen

### Ključne kode spremembe

#### 1. `TenantMiddleware` – identifikacija tenanta

```python
class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Iz subdomene: s59dgo.clanstvo.zrs.si → "s59dgo"
        host = request.headers.get("host", "")
        tenant_id = host.split(".")[0] if "." in host else None

        # Validacija: tenant mora obstajati
        if tenant_id and tenant_id != "admin":
            if not _tenant_exists(tenant_id):
                return Response("Klub ne obstaja", status_code=404)
            request.state.tenant_id = tenant_id
        else:
            request.state.tenant_id = None  # super-admin kontekst

        return await call_next(request)
```

#### 2. `DynamicDBMiddleware` – dinamična DB seja

```python
# Vsak tenant ima svojo SQLAlchemy engine instanco
_tenant_engines: dict[str, Engine] = {}

def get_tenant_engine(tenant_id: str) -> Engine:
    if tenant_id not in _tenant_engines:
        db_path = f"data/{tenant_id}/clanstvo.db"
        os.makedirs(f"data/{tenant_id}", exist_ok=True)
        engine = create_engine(f"sqlite:///{db_path}", ...)
        Base.metadata.create_all(bind=engine)
        _migriraj_bazo(engine)  # obstoječa funkcija
        _tenant_engines[tenant_id] = engine
    return _tenant_engines[tenant_id]

def get_db(request: Request):
    engine = get_tenant_engine(request.state.tenant_id)
    db = SessionLocal(bind=engine)
    try:
        yield db
    finally:
        db.close()
```

#### 3. Ločitev `get_db` dependency

Obstoječe `Depends(get_db)` v vseh routerjih deluje **brez sprememb** – samo implementacija `get_db` se zamenja, da vrne tenant-specifično sejo. To je ključna prednost obstoječe arhitekture z dependency injection.

#### 4. Session izolacija

Session piškotki morajo biti ločeni per tenant. Enostavna rešitev: vsak tenant dobi ločen `SECRET_KEY` (generiran ob kreiranju tenanta in shranjen v super-admin bazi) ali pa se v session key doda tenant prefix:

```python
# Opcija A: ločen secret per tenant (boljše)
secret = get_tenant_secret(tenant_id)  # iz super-admin baze
app.add_middleware(SessionMiddleware, secret_key=secret, ...)

# Opcija B: tenant v session key (zadostuje za začetek)
session_key = f"{tenant_id}:{session_data['uporabnik']}"
```

#### 5. CSRF in Jinja2 globals

Ostanejo enaki – delujejo per-request, torej so tenant-agnostični.

#### 6. Audit log

Vsak tenant ima svojo `audit_log` tabelo v svoji bazi – izolacija je inherentna.

---

### Struktura datotek

```
UpravljanjeClanstva/
├── app/
│   ├── main.py             – + TenantMiddleware, DynamicDBMiddleware
│   ├── tenant.py           – nova: tenant management helpers
│   ├── super_admin/        – nova: super-admin routerji in templates
│   │   ├── router.py
│   │   └── templates/
│   ├── database.py         – posodobljen: dynamic engine per tenant
│   └── ...                 – ostalo nespremenjeno
├── data/
│   ├── super_admin.db      – super-admin baza (tenanti, super_admin_log)
│   ├── s59dgo/
│   │   └── clanstvo.db
│   ├── s59abc/
│   │   └── clanstvo.db
│   └── s59xyz/
│       └── clanstvo.db
├── docker-compose.yml      – posodobljen (1 vsebnik)
└── nginx.conf              – wildcard subdomain config
```

---

## 4. Alternativa za večjo skalo (Option C)

Če bi ZRS kdaj prerasla 100 klubov ali potrebovala cross-tenant analitiko, bi bila selitev na PostgreSQL s shemami smiselna.

### Ključne spremembe pri migraciji SQLite → PostgreSQL

1. **SQLAlchemy dialect**: `sqlite://` → `postgresql://` (večinoma kompatibilno)
2. **`_migriraj_bazo()`** zamenjati z Alembic migration per shema
3. **`create_schema` pri kreiranju tenanta**: `CREATE SCHEMA s59dgo; SET search_path = s59dgo;`
4. **Connection string per tenant**: `postgresql://user:pass@host/clanstvo?options=-c search_path=s59dgo`
5. **Async SQLAlchemy** priporočen pri PostgreSQL za boljšo sočasnost

### SQLite → PostgreSQL kompatibilnostne pasti

| SQLite specifika | PostgreSQL ekvivalent |
|------------------|-----------------------|
| `INTEGER PRIMARY KEY` (autoincrement) | `SERIAL` ali `BIGSERIAL` |
| `BOOLEAN` kot 0/1 | nativni `BOOLEAN` |
| `func.now()` | dela enako |
| `text()` raw SQL migracije | bolj strogo tipiziran SQL |
| `REAL` za float | `DOUBLE PRECISION` |
| Brez sheme po privzetem | `SET search_path = tenant_id` |

**Portabilnost se izgubi**: klub ne more vzeti PostgreSQL sheme in jo neposredno poganjati kot SQLite. Potreben bi bil `pg_dump | sqlite-convert` pipeline. Za klube, ki bi hoteli standalone, bi bilo treba ohraniti SQLite izvoz (prek obstoječega Excel backup ali posebnega DB dump endpointa).

---

## 5. Super-admin tier

Super-admin je popolnoma ločen od tenant adminov. Dostopa samo do meta-podatkov (seznam tenantov), nikoli do vsebinskih podatkov kluba.

### Super-admin baza (`data/super_admin.db`)

```
tenanti
├── id (TEXT PK) – klicni znak: "s59dgo"
├── ime – polno ime kluba
├── aktiven (BOOL)
├── ustvarjen_cas (DateTime)
└── opombe

super_admin_log
├── id (PK)
├── cas
├── akcija – "tenant_ustvarjen", "tenant_deaktiviran", "admin_kreiran"
└── opis
```

### Super-admin akcije

| Akcija | Opis |
|--------|------|
| Ustvari tenant | Vnesi klicni znak + ime kluba → ustvari mapo `data/<id>/`, inicializira DB, kreira prvega admin računa |
| Deaktiviraj tenant | Blokira dostop (HTTP 403 za vse zahteve tega tenanta), DB ostane |
| Reaktiviraj tenant | Obnovi dostop |
| Pregled tenantov | Seznam klubov z datumom kreacije in statusom (brez vsebinskih podatkov!) |
| Audit log | Pregled super-admin akcij (brez vpogleda v tenant audit loge) |

### Kaj super-admin **ne more** videti

- Članov posameznega kluba
- Plačil, aktivnosti, skupin
- Uporabniških računov v klubu (razen lastnega kreiranja prvega admina)
- Audit loga posameznega kluba

Ta omejitev je arhitekturno zagotovljena: super-admin `get_db` dependency vrne **super-admin bazo**, nikoli tenant baze.

### Super-admin dostop

Super-admin bi bil dostopen na ločeni subdomeni:

```
https://admin.clanstvo.zrs.si
```

Z lastno prijavo (ločeni `Uporabnik` zapisi v `super_admin.db`). Session piškotki za super-admin in tenant admin so ločeni (ločeni secret_key ali ločeni cookie name).

---

## 6. URL in routing strategija

### Varianta 1: Subdomena per klub (priporočeno)

```
s59dgo.clanstvo.zrs.si   →  klub S59DGO
s59abc.clanstvo.zrs.si   →  klub S59ABC
admin.clanstvo.zrs.si    →  super-admin
```

**Nginx konfiguracija (wildcard):**

```nginx
server {
    listen 443 ssl http2;
    server_name *.clanstvo.zrs.si;

    ssl_certificate     /etc/letsencrypt/live/clanstvo.zrs.si/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/clanstvo.zrs.si/privkey.pem;

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }
}
```

**Let's Encrypt wildcard certifikat** zahteva DNS-01 challenge (ne HTTP-01). Potreben je DNS provider z API-jem (npr. Cloudflare, Route53) ali ročna obnova. Certbot to podpira prek pluginov.

**Prednosti subdomene:**
- Čisti URL-ji: `s59dgo.clanstvo.zrs.si/clani` (ne `/s59dgo/clani`)
- Preprost TenantMiddleware (parsiranje subdomene)
- Jasna vizualna ločitev za uporabnike

### Varianta 2: URL path prefix per klub

```
clanstvo.zrs.si/klubi/s59dgo/clani
clanstvo.zrs.si/klubi/s59abc/clani
```

**Prednosti:**
- Enostavnejši certifikat (standardni, brez wildcard)
- Enostavnejši DNS

**Slabosti:**
- Vsi FastAPI routerji dobijo prefix `/klubi/{tenant_id}/` → obsežne spremembe vseh URL-jev
- Težje ločiti super-admin od tenant dostopov
- Manj intuitiven URL za klube

**Priporočilo:** Subdomena je boljša izkušnja, wildcard certifikat ni problematičen na modernem DNS.

---

## 7. Ocena dela po opcijah

### Option A – Več Docker instanc

| Naloga | Ocena |
|--------|-------|
| Nginx config za wildcard subdomain | 0.5 dneva |
| Bash skripta za kreiranje nove instance | 1 dan |
| Dokumentacija postopka | 0.5 dneva |
| **Skupaj** | **~2 dneva** |

Ni super-admin vmesnika – vse se dela ročno s skripti ali docker-compose.

### Option B – Ena instanca, ločene SQLite ✅

| Naloga | Ocena |
|--------|-------|
| `TenantMiddleware` + `DynamicDBMiddleware` | 1 teden |
| Posodobitev `get_db` dependency + testiranje | 3 dni |
| Session izolacija per tenant | 3 dni |
| Super-admin baza + modeli | 3 dni |
| Super-admin UI (seznam tenantov, kreiranje) | 1 teden |
| Tenant provisioning (kreiranje mape, DB, prvega admina) | 3 dni |
| Nginx wildcard + wildcard certifikat | 2 dni |
| KlubContextMiddleware posodobitev (per-tenant) | 1 dan |
| End-to-end testiranje (10+ tenantov) | 1 teden |
| Dokumentacija + deployment guide | 3 dni |
| **Skupaj** | **~6–9 tednov** |

### Option C – PostgreSQL sheme

| Naloga | Ocena |
|--------|-------|
| Vse iz Option B | 6–9 tednov |
| SQLite → PostgreSQL migracija | 3 tedni |
| Alembic setup per shema | 1 teden |
| Async SQLAlchemy (opcijsko za perf) | 1 teden |
| PostgreSQL Docker + backup setup | 3 dni |
| **Skupaj** | **~13–18 tednov** |

---

## 8. Varnost in GDPR

### GDPR implikacije multi-tenant arhitekture

| Zahteva | Option B (SQLite) | Option C (PG sheme) |
|---------|-------------------|---------------------|
| Fizična izolacija podatkov | ✅ Ločene `.db` datoteke | ✅ Ločene sheme |
| Backup samo za lasten klub | ✅ Trivialen | ✅ `pg_dump --schema` |
| Brisanje tenanta (GDPR čl. 17) | ✅ `rm -rf data/s59dgo/` | ✅ `DROP SCHEMA s59dgo CASCADE` |
| Super-admin brez vpogleda v podatke | ✅ Arhitekturno zagotovljeno | ✅ Arhitekturno zagotovljeno |
| Revizijska sled per klub | ✅ Vsak klub ima svojo `audit_log` | ✅ Isto |
| Šifriranje v mirovanju (encryption at rest) | ⚠️ OS-level FDE priporočen | ⚠️ OS-level FDE priporočen |

### Šifriranje podatkov (encryption at rest)

Aplikacijska-nivojska enkripcija podatkov (šifriranje posameznih stolpcev v DB) **ni priporočena** za ta primer:

- Dodaja kompleksnost brez bistvene prednosti (aplikacija mora podatke vseeno dešifrirati za prikaz)
- Otežuje iskanje in filtriranje
- Ključi morajo biti nekje shranjeni – prenesejo problem drugam

**Priporočena alternativa:** Linux disk encryption (LUKS) na strežniku za encryption at rest. To je transparentno za aplikacijo, zagotavlja varstvo pri fizični kraji strežnika, in je standardna praksa.

```bash
# Primer: šifriran volumen samo za data/
cryptsetup luksFormat /dev/sdb
cryptsetup open /dev/sdb clanstvo-data
mkfs.ext4 /dev/mapper/clanstvo-data
mount /dev/mapper/clanstvo-data /opt/radioklub/data
```

### Varnostni premisleki specifični za multi-tenant

1. **Tenant enumeration**: Middleware mora preprečiti, da napadalec ugotovi katere subdomene/tenant IDs obstajajo. Neobstoječ tenant → generičen 404 brez razkritja.
2. **Session cookie contamination**: Session za `s59dgo` ne sme biti veljavna za `s59abc`. Zagotovljeno z ločenimi secret_key ali cookie `domain` atributom (`.s59dgo.clanstvo.zrs.si`).
3. **Path traversal v tenant_id**: `tenant_id` mora biti validiran z allowlist regex (`^[a-z0-9]{3,10}$`) pred uporabo v file path-u.
4. **Super-admin kompromitacija**: Ker super-admin lahko kreira admin račune, je kompromitacija super-admin računa visoko tvegana. Priporočena obvezna 2FA za super-admin.
5. **Rate limiting per tenant**: Obstoječ rate limiting `_login_attempts` dict je global. Za multi-tenant ga je treba ločiti: `{tenant_id}:{ip} → [timestamps]`.

---

## 9. Docker in infrastruktura

### Option B: Docker Compose (ena instanca)

```yaml
services:
  clanstvo:
    build: .
    container_name: radioklub-clanstvo-multi
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      - ./data:/app/data          # vsebuje vse tenant baze
    environment:
      - SECRET_KEY_MASTER=${SECRET_KEY_MASTER}   # za super-admin sejo
      - ADMIN_GESLO=${ADMIN_GESLO}               # za prvega super-admina
      - OKOLJE=produkcija
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c",
             "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
```

**Volume struktura:**
```
./data/
├── super_admin.db            ← super-admin baza
├── s59dgo/
│   └── clanstvo.db
├── s59abc/
│   └── clanstvo.db
└── ...
```

**Backup strategija:**
```bash
# Dnevni backup vseh tenantov (cron)
#!/bin/bash
DATE=$(date +%Y%m%d)
BACKUP_DIR=/backup/radioklub/$DATE
mkdir -p $BACKUP_DIR

# Super-admin baza
cp /opt/radioklub/data/super_admin.db $BACKUP_DIR/

# Vse tenant baze
for tenant_dir in /opt/radioklub/data/*/; do
    tenant=$(basename $tenant_dir)
    if [ -f "$tenant_dir/clanstvo.db" ]; then
        mkdir -p $BACKUP_DIR/$tenant
        cp $tenant_dir/clanstvo.db $BACKUP_DIR/$tenant/
    fi
done

# Kompresija
tar -czf $BACKUP_DIR/../radioklub_$DATE.tar.gz $BACKUP_DIR/
rm -rf $BACKUP_DIR

# Brisanje backupov starejših od 30 dni
find /backup/radioklub/ -name "*.tar.gz" -mtime +30 -delete
```

### Sistemske zahteve za 50 tenantov (Option B)

| Vir | Minimalno | Priporočeno |
|-----|-----------|-------------|
| RAM | 2 GB | 4 GB |
| CPU | 2 jedri | 4 jedra |
| Disk | 10 GB | 50 GB (z backupi) |
| OS | Ubuntu 22.04 LTS | Ubuntu 24.04 LTS |

Za primerjavo – Option A pri 50 tenantih bi zahteval ~3–5 GB RAM samo za procese.

---

## 10. Portabilnost – exit strategija

Zahteva je, da klub, ki bi zapustil ZRS centralni sistem (ali bi ZRS ugasnila servis), vzame svoje podatke in zažene lastno instanco.

### Option B (SQLite): Postopek portacije

```bash
# Na ZRS strežniku: izvoz podatkov kluba
cp /opt/radioklub/data/s59dgo/clanstvo.db /tmp/s59dgo_export.db

# Klub dobi: s59dgo_export.db
# Klub postavi lastno instanco (obstoječa standalone aplikacija):
cp s59dgo_export.db data/clanstvo.db
docker compose up -d --build
```

**Rezultat:** 100% podatkov, 100% funkcionalna aplikacija, brez nobene konverzije. To je ena od ključnih prednosti Option B.

### Option C (PostgreSQL): Postopek portacije

```bash
# Izvoz iz PostgreSQL sheme
pg_dump --schema=s59dgo --no-owner radioklub_db > s59dgo_dump.sql

# Konverzija v SQLite (zahteva pgloader ali lasten skript)
pgloader s59dgo_dump.sql sqlite:///clanstvo.db

# Ali: aplikacija bi morala imeti SQLite export endpoint
```

Manj zanesljivo, zahteva dodatna orodja in testiranje. Portabilnost je oslabljena.

---

## 11. Tveganja in odprta vprašanja

### Tehnična tveganja

| Tveganje | Verjetnost | Vpliv | Mitigacija |
|----------|-----------|-------|-----------|
| SQLite file locking pri sočasnih zahtevah istega tenanta | Srednja | Srednji | WAL journal mode (`PRAGMA journal_mode=WAL`) |
| Engine cache raste neomejeno pri 100+ tenantih | Nizka | Nizek | LRU cache z max 200 engine instancami, idle close |
| Path traversal napad prek tenant_id | Nizka | Visok | Regex allowlist validacija tenant_id |
| Wildcard SSL cert obnova (DNS-01 challenge) | Nizka | Visok | Cloudflare DNS plugin za Certbot, automatizirano |
| Session cookie napačen tenant (browser cache) | Nizka | Srednji | Cookie `domain` ekspliciten per subdomena |

### Odprta vprašanja za ZRS

1. **Kako se klubi registrirajo?** Ročna kreacija s strani ZRS super-admina ali self-service obrazec?
2. **Plačljivost/freemium?** Ni del te evaluacije, a vpliva na arhitekturo (activation flow, suspension).
3. **DNS upravljanje**: Ali bo ZRS upravljala DNS za `clanstvo.zrs.si` in wildcard? Ali bodo imeli klubi lastne domene (zahteva per-tenant certifikat)?
4. **SLA in uptime**: Kakšna je pričakovana razpoložljivost? En strežnik brez HA je single point of failure za vse klube.
5. **Testni/staging okolji**: Ali bo vsak klub imel testno instanco ali samo produkcijsko?

### Priporočilo glede staging/HA

Za 50+ klubov, ki se zanašajo na en strežnik, je priporočena vsaj:
- **Dnevni off-site backup** (rsync na drug strežnik ali S3-kompatibilen storage)
- **Monitoring** (Uptime Kuma ali podobno) z alertiranjem
- **Dokumentiran recovery postopek** (kako se obnovi iz backupa v <2h)

Visoka razpoložljivost (active-active cluster) je pri tej skali in naravi aplikacije verjetno pretirano – KISS princip velja.

---

## Povzetek

Za 20–100 klubov s kritično GDPR izolacijo in zahtevo po portabilnosti je **Option B (ena instanca, ločene SQLite baze)** optimalna izbira.

**Ocena dela: 6–9 tednov** za izkušenega Python/FastAPI razvijalca, ki pozna obstoječo kodo.

Ključna prednost pred Option A je operativna preprostost (en vsebnik, en deployment), pred Option C pa ohranitev SQLite arhitekture in s tem trivialna portabilnost ter manjši obseg dela. Pred Option D jo ločuje fizična podatkovna izolacija, ki je pogoj za GDPR.

```
Priporočena pot:
1. Option B implementacija (6–9 tednov)
2. Wildcard subdomain + Certbot DNS-01 challenge
3. Super-admin UI (minimalen: kreiranje tenantov, prikaz statusa)
4. Samodejni backup skript (cron, off-site)
5. Monitoring + alertiranje
```

*Dokument je evaluacija, ne implementacijska specifikacija. Pred pričetkom razvoja priporočam PoC (proof of concept) za TenantMiddleware + DynamicDBMiddleware v izoliranem branch-u.*
