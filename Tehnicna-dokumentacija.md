# Tehnična dokumentacija – Radio klub Člani

*Različica 1.12 | Datum: 2026-02-24*

---

## Kazalo

1. [Pregled arhitekture](#1-pregled-arhitekture)
2. [Sistemske zahteve](#2-sistemske-zahteve)
3. [Namestitev z Dockerjem](#3-namestitev-z-dockerjem)
   - [Linux x64 (Ubuntu / Debian)](#31-linux-x64-ubuntu--debian)
   - [Raspberry Pi (ARM64)](#32-raspberry-pi-arm64)
   - [Mac z Apple Silicon (ARM)](#33-mac-z-apple-silicon-arm)
   - [Synology NAS Intel](#34-synology-nas-intel)
4. [Konfiguracija (.env)](#4-konfiguracija-env)
5. [HTTPS z Nginx reverse proxy](#5-https-z-nginx-reverse-proxy)
6. [Vzdrževanje](#6-vzdrževanje)
7. [Posodobitev aplikacije](#7-posodobitev-aplikacije)
8. [CI/CD – GitHub Actions in Container Registry](#8-cicd--github-actions-in-container-registry)
9. [Lokalni razvoj brez Dockerja](#9-lokalni-razvoj-brez-dockerja)
10. [Arhitektura podatkovnega modela](#10-arhitektura-podatkovnega-modela)
11. [Varnostne opombe](#11-varnostne-opombe)
12. [Testi](#12-testi)

---

## 1. Pregled arhitekture

```
Brskalnik
    │ HTTP(S)
    ▼
[Nginx reverse proxy]   ← opcijsko, za HTTPS in javni dostop
    │
    ▼
FastAPI (uvicorn)       ← Python 3.12, port 8000
    │
    ├── Jinja2 templates  ← server-side rendering
    ├── SQLAlchemy ORM    ← dostop do baze
    │       │
    │       ▼
    │   SQLite            ← data/clanstvo.db (Docker volume ./data/)
    │
    └── openpyxl          ← uvoz/izvoz Excel
```

### Ključne komponente

| Komponenta | Tehnologija | Verzija |
|------------|-------------|---------|
| Backend | Python + FastAPI | 3.12 / 0.115 |
| ASGI strežnik | uvicorn[standard] | 0.32 |
| Baza podatkov | SQLite prek SQLAlchemy | 2.0 |
| Predloge | Jinja2 | 3.1 |
| Avtentikacija | SessionMiddleware + bcrypt | — |
| 2FA (TOTP) | pyotp + segno (SVG QR) | 2.9 / 1.6 |
| Kontekst kluba | KlubContextMiddleware → request.state | — |
| Frontend | Bootstrap 5.3 + DataTables + Bootstrap Icons | CDN |
| Excel | openpyxl | 3.1 |

### Struktura map

```
UpravljanjeClanstva/
├── app/
│   ├── main.py           – FastAPI app, middleware (Security, Session, KlubContext), login/logout, migracije
│   ├── database.py       – SQLite engine, get_db()
│   ├── models.py         – SQLAlchemy modeli
│   ├── auth.py           – gesla, vloge, zaščita endpointov
│   ├── config.py         – branje nastavitev iz baze
│   ├── csrf.py           – CSRF token zaščita
│   ├── audit_log.py      – log_akcija() helper
│   ├── routers/          – FastAPI routerji po področjih
│   ├── templates/        – Jinja2 HTML predloge
│   └── static/           – CSS, ikone
├── data/                 – SQLite baza (Docker volume, ni v image-u)
│   └── clanstvo.db
├── tests/                – pytest testi
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── requirements-dev.txt
└── .env.example
```

---

## 2. Sistemske zahteve

### Za namestitev z Dockerjem

| Platforma | Minimalne zahteve |
|-----------|-------------------|
| Linux x64 | Docker Engine 24+, Docker Compose v2, 512 MB RAM |
| Raspberry Pi | Pi 3B+ ali novejši (ARM64), Docker Engine 24+, 512 MB RAM |
| Mac ARM | Docker Desktop 4.x (Apple Silicon) |
| Synology NAS Intel | DSM 7.2+, Container Manager 2.x |

> **Raspberry Pi Zero in Pi 1** nista podprta – Python 3.12 slim image ne podpira ARMv6.

### Za lokalni razvoj (brez Dockerja)

- Python 3.12+
- pip

---

## 3. Namestitev z Dockerjem

### Splošni koraki za vse platforme

Pred namestitvijo pridobite kodo aplikacije (klonirajte repozitorij ali prekopirajte mapo) in ustvarite `.env` datoteko:

```bash
cp .env.example .env
```

Uredite `.env` z ustreznimi vrednostmi (obvezno `SECRET_KEY` in `ADMIN_GESLO` – glejte [poglavje 4](#4-konfiguracija-env)).

---

### 3.1 Linux x64 (Ubuntu / Debian)

#### Predpogoj: namestitev Dockerja

```bash
# Posodobi pakete in namesti odvisnosti
sudo apt update && sudo apt install -y ca-certificates curl gnupg

# Dodaj Docker GPG ključ in repozitorij
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list

# Namesti Docker in Compose
sudo apt update && sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Dodaj trenutnega uporabnika v skupino docker (brez sudo)
sudo usermod -aG docker $USER
newgrp docker
```

#### Zagon aplikacije

```bash
# Premaknite se v mapo z aplikacijo
cd /opt/radioklub-clanstvo   # ali katerakoli lokacija

# Ustvarite in uredite .env
cp .env.example .env
nano .env

# Ustvarite mapo za bazo podatkov
mkdir -p data && chmod 777 data

# Zaženite (image se samodejno prenese iz GHCR)
docker compose up -d

# Preverite status
docker compose ps
docker compose logs -f
```

Aplikacija je dostopna na `http://localhost:8000` (samo lokalno). Za dostop z omrežja glejte [poglavje 5](#5-https-z-nginx-reverse-proxy).

#### Samodejni zagon ob zagonu sistema

`restart: unless-stopped` v `docker-compose.yml` poskrbi, da se vsebnik samodejno zažene po ponovnem zagonu strežnika.

---

### 3.2 Raspberry Pi (ARM64)

Podprti modeli: **Pi 3B+, Pi 4, Pi 5, Pi Zero 2 W** (ARM64 / aarch64).

#### Predpogoj: namestitev Dockerja na Pi

```bash
# Priporočen način za Raspberry Pi OS (64-bit)
curl -fsSL https://get.docker.com | sudo sh

# Dodaj pi v skupino docker
sudo usermod -aG docker pi
newgrp docker

# Preveri verzijo
docker --version
docker compose version
```

#### Prilagoditev Dockerfila (ni potrebna)

`python:3.12-slim` je **multi-arch** image in podpira ARM64 nativno – ni treba spreminjati `Dockerfile`.

#### Zagon aplikacije

```bash
cd ~/radioklub-clanstvo
cp .env.example .env
nano .env

# Ustvarite mapo za bazo podatkov
mkdir -p data && chmod 777 data

# Zaženite (image se samodejno prenese iz GHCR)
docker compose up -d

# Preverite
docker compose ps
```

> **Namig za Pi:** Baza podatkov se nahaja v `./data/clanstvo.db`. Za zanesljivo delovanje priporočamo shranjevanje na SSD (USB) namesto na SD kartico, ki je bolj dovzetna za poškodbe ob izpadu napajanja.

```bash
# Primer premika data mape na USB SSD na /mnt/ssd
mkdir -p /mnt/ssd/radioklub/data
# V docker-compose.yml spremenite volume:
#   - /mnt/ssd/radioklub/data:/app/data
```

---

### 3.3 Mac z Apple Silicon (ARM)

#### Predpogoj: Docker Desktop

Prenesite in namestite **Docker Desktop for Mac** (Apple Silicon verzija) z uradne strani Docker.

Po namestitvi zagotovite, da je Docker Desktop zagnan (ikona v menijski vrstici).

#### Zagon aplikacije

```bash
# V Terminalu
cd ~/Projekti/radioklub-clanstvo   # ali kjer je aplikacija

cp .env.example .env
open -e .env   # uredi v TextEditu, ali uporabite nano/vim

mkdir -p data && chmod 777 data
docker compose up -d

# Preverite
docker compose ps
docker compose logs -f
```

Aplikacija je dostopna na `http://localhost:8000`.

> `python:3.12-slim` vsebuje ARM64 plast – gradnja je nativna in hitra (< 1 min na M-čipu).

#### Samodejni zagon

Docker Desktop ima vgrajeno nastavitev **"Start Docker Desktop when you log in"**. Vsebniki z `restart: unless-stopped` se zaženejo samodejno ob zagonu Docker Desktop-a.

---

### 3.4 Synology NAS Intel

Podprti modeli z Intel/AMD64 procesorjem: DS223+, DS723+, DS923+, DS1522+, RS422+ in drugi z DSM 7.2+.

Na Synology je mogoče aplikacijo zagnati na dva načina: prek grafičnega vmesnika Container Manager ali prek SSH.

---

#### Način A: Container Manager (grafični vmesnik)

**Predpogoj:** V **Package Center** namestite **Container Manager**.

**Korak 1 – Prenesite kodo na NAS**

Prenesite zip arhiv aplikacije in ga razpakirajte v skupno mapo, npr. `/volume1/docker/radioklub-clanstvo/`.

Prek **File Station** → naložite vse datoteke aplikacije.

**Korak 2 – Ustvarite .env datoteko**

Prek SSH (Putty / Terminal) ali File Station uredite oz. ustvarite `.env`:

```
SECRET_KEY=<vaš-dolg-naključni-niz>
ADMIN_GESLO=<varno-geslo>
OKOLJE=produkcija
KLUB_IME=<polno ime kluba>
KLUB_OZNAKA=<klicni znak>
```

**Korak 3 – Ustvarite projekt**

1. Odprite **Container Manager** → **Project** → **Create**.
2. Izberite **Build from docker-compose.yml**.
3. V polju **Path** izberite mapo `/volume1/docker/radioklub-clanstvo/`.
4. Potrdite nastavitve in kliknite **Build**.

**Korak 4 – Preverite dostopnost**

Aplikacija je dostopna na `http://<IP-NAS>:8000` znotraj lokalnega omrežja.

---

#### Način B: SSH (priporočen za napredne)

**Predpogoj:** V **Control Panel → Terminal & SNMP** omogočite SSH dostop.

```bash
# Povežite se na NAS
ssh admin@192.168.1.x

# Premaknite se v mapo z aplikacijo
cd /volume1/docker/radioklub-clanstvo

# Ustvarite .env
cp .env.example .env
vi .env   # uredite vrednosti

# OBVEZNO: ustvarite mapo za bazo podatkov pred prvim zagonom
# (Docker je ne ustvari samodejno, vsebnik pa teče kot neprivilegirani uporabnik)
mkdir -p data && chmod 777 data

# Zaženite (Docker Compose je na DSM 7 del Container Manager)
docker compose up -d

# Preverite – aplikacija je dostopna na http://<IP-NAS>:8080
docker compose ps
docker compose logs --tail=20
```

> **Opomba za port:** V `docker-compose.yml` nastavite port na `<IP-NAS>:8080:8000` ali samo `8080:8000` (ne `127.0.0.1:8080:8000`, ker s tem port ostane dostopen samo lokalno na NAS-u in ne iz omrežja). Aplikacijo dosežete na `http://<IP-NAS>:8080`, ne `http://localhost:8080`.

---

#### Synology Reverse Proxy (za dostop z URL-jem in HTTPS)

Za dostop prek `https://clanstvo.vasadomena.si` ali `https://NAS:443/clanstvo`:

1. **Control Panel → Login Portal → Advanced → Reverse Proxy**
2. Kliknite **Create**:
   - **Source protocol:** HTTPS, vrata 443, ime gostitelja (npr. `clanstvo.vasdns.synology.me`)
   - **Destination:** HTTP, `localhost`, vrata `8000`
3. Na zavihku **Custom Header** dodajte:
   - `X-Forwarded-For` → `$proxy_add_x_forwarded_for`
   - `X-Real-IP` → `$remote_addr`
4. Za HTTPS certifikat: **Control Panel → Security → Certificate** → ustvarite Let's Encrypt certifikat za vašo domeno.

> **Opomba za Synology QuickConnect:** QuickConnect ne podpira posredovanja za aplikacije na netandardnih portih. Priporočamo Synology DDNS + Let's Encrypt + Reverse Proxy.

---

## 4. Konfiguracija (.env)

Pred zagonom kopirajte `.env.example` v `.env` in nastavite vse vrednosti.

```bash
cp .env.example .env
```

### Spremenljivke okolja

| Spremenljivka | Obvezno | Opis | Primer |
|--------------|---------|------|--------|
| `SECRET_KEY` | **DA** | Ključ za podpisovanje session piškotkov. Mora biti dolg (32+ znakov), naključen, edinstven. | `openssl rand -hex 32` |
| `ADMIN_GESLO` | **DA** | Geslo privzetega admin računa ob **prvi** namestitvi. Po namestitvi zamenjajte prek UI. | `MojeGeslo123!XY` |
| `OKOLJE` | ne | `razvoj` ali `produkcija`. V produkciji se gesla ne izpisujejo v loge. | `produkcija` |
| `KLUB_IME` | ne | Polno ime kluba. Nastavljivo tudi prek UI (Nastavitve). | `Radio klub Primer` |
| `KLUB_OZNAKA` | ne | Klicni znak kluba. Prikazuje se v navigacijski vrstici. Nastavljivo tudi prek UI. | `S5XYZ` |

### Generiranje SECRET_KEY

```bash
# Z Pythonom
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Ali z opensslom
openssl rand -hex 32
```

### Primer `.env`

```ini
SECRET_KEY=kHFz8rXp2mNqL9tVbJ0yE5wA3uGcD7sI1oP6hY4
ADMIN_GESLO=MojVarnoGeslo2025!
OKOLJE=produkcija
KLUB_IME=Radio klub Primer
KLUB_OZNAKA=S5XYZ
```

> **Opomba:** `KLUB_IME` in `KLUB_OZNAKA` sta opcijski – klub in oznako je mogoče nastaviti tudi prek spletnega vmesnika **Nastavitve** po prvi prijavi. Vrednosti v `.env` se upoštevajo samo ob prvi namestitvi (ko nastavitev v bazi še ne obstaja).

> **.env datoteke ne smete shraniti v git repozitorij.** Preverite, da je `.env` vnesen v `.gitignore`.

---

## 5. HTTPS in javni dostop

### Tipična uporaba – lokalno omrežje ali VPN

Za večino radioklubov je aplikacija dostopna samo znotraj lokalnega omrežja ali prek VPN. V tem primeru **HTTPS ni potreben** – promet ne zapusti zaupljivega omrežja in aplikacija deluje varno brez sprememb.

### Javni dostop prek interneta

Kadar je aplikacija dostopna iz javnega interneta, je HTTPS obvezen. Vso varnostno konfiguracijo (SSL, HSTS) uredite na **reverse proxy-u** – kode aplikacije ni treba spreminjati.

#### HSTS (Strict-Transport-Security)

HSTS header pove brskalniku, naj za to domeno vedno uporablja HTTPS in nikoli ne pošlje piškotkov po HTTP. To zadostuje za popolno zaščito session cookijev – ni treba posegati v kodo aplikacije.

---

### 5A. Synology NAS – Let's Encrypt in vgrajen reverse proxy

Ta postopek velja za Synology NAS z DSM 7.2+ na katerem že tečejo druge storitve. Vsaka domena ima lasten certifikat in lastno reverse proxy pravilo – obstoječe storitve se ne spremenijo.

Primer spodaj uporablja domeno `clani.s59dgo.org` – zamenjajte z dejansko domeno vašega kluba.

#### Predpogoj: Port forwarding na usmerjevalniku

Let's Encrypt za pridobitev certifikata potrebuje **port 80** (HTTP-01 challenge). Poleg 443, ki je verjetno že preusmerjen, dodajte še port 80:

| Ime | Zunanji port | Protokol | Destinacija (IP NAS-a) | Interni port |
|-----|-------------|----------|------------------------|-------------|
| NAS-HTTPS | 443 | TCP | 192.168.x.x | 443 |
| NAS-HTTP | 80 | TCP | 192.168.x.x | 80 |

> Port 80 mora ostati odprt – Synology DSM ga potrebuje za samodejno obnovo certifikata (vsake 90 dni).

#### Korak 1: Pridobi Let's Encrypt certifikat

**DSM → Control Panel → Security → Certificate → Add**

1. Kliknite **Add** → **Add a new certificate** → **Next**
2. Izberite: **Get a certificate from Let's Encrypt**
3. Vnesite:
   - **Domain name:** `clani.s59dgo.org`
   - **Email:** vaš e-naslov (za obvestila o obnovi)
   - **Subject Alternative Name:** pustite prazno
4. Kliknite **Apply**

DSM bo kontaktiral Let's Encrypt, opravil HTTP challenge in shranil certifikat. Postopek traja ~30 sekund.

> Če imate wildcard certifikat (`*.s59dgo.org`), ki že pokriva `clani.s59dgo.org`, ta korak preskočite.

#### Korak 2: Nastavi Reverse Proxy

**DSM → Control Panel → Login Portal → Advanced → Reverse Proxy → Create**

Izpolnite polja:

| Polje | Vrednost |
|-------|----------|
| Reverse Proxy Name | `clani-s59dgo` |
| Protocol (Source) | `HTTPS` |
| Hostname | `clani.s59dgo.org` |
| Port | `443` |
| Protocol (Destination) | `HTTP` |
| Hostname | `localhost` |
| Port | `8000` |

> Preverite kateri port ima vaš Docker container. V `docker-compose.yml` poiščite vrstico `ports`. Če imate `- "8080:8000"`, je destinacijski port `8080`.

Po ustvaritvi pravila kliknite **Edit** → zavihek **Custom Header** → **Create** → **Header**:

| Header Name | Header Value |
|-------------|-------------|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` |

Kliknite **Save**.

> **Opomba glede `includeSubDomains`:** Če imate na isti domeni druge subdomene brez HTTPS, uporabite samo `max-age=31536000`.

#### Korak 3: Dodeli certifikat domeni

**DSM → Control Panel → Security → Certificate → Configure**

V seznamu poiščite vrstico `clani.s59dgo.org` (reverse proxy service) in ji dodelite certifikat `clani.s59dgo.org` (Let's Encrypt, pridobljen v koraku 1).

Obstoječe storitve na NAS-u ohranijo svoje certifikate – vsaka domena je neodvisna.

#### Korak 4: Preveri Docker port binding

Synology reverse proxy komunicira z Dockerjem interno, zato mora biti port dostopen na `localhost`. Preverite `docker-compose.yml`:

```yaml
# Pravilno – dostopno lokalno na NAS-u (priporočeno):
ports:
  - "127.0.0.1:8000:8000"

# Ali brez IP omejitve (bolj ohlapno, a deluje):
ports:
  - "8000:8000"
```

Če ste med namestitvijo nastavili specifičen IP NAS-a (npr. `192.168.3.6:8080:8000`), ga zamenjajte nazaj na `127.0.0.1:8000:8000`, saj bo do aplikacije dostopala samo Synology (ne neposredno iz omrežja):

```bash
# Na NAS-u v mapi z docker-compose.yml:
docker compose down && docker compose up -d
```

#### Korak 5: Preizkus

```bash
# HTTP → HTTPS redirect (Synology to naredi samodejno)
curl -I http://clani.s59dgo.org
# Pričakovano: 301 Moved Permanently → https://clani.s59dgo.org

# HTTPS z veljavnim certifikatom
curl -I https://clani.s59dgo.org
# Pričakovano: 200 OK

# Preveri HSTS header
curl -I https://clani.s59dgo.org | grep -i strict
# Pričakovano: strict-transport-security: max-age=31536000; includeSubDomains
```

Ali v brskalniku: `https://clani.s59dgo.org` → zelena ključavnica.

#### Obnova certifikata

Synology DSM certifikat samodejno obnovi 30 dni pred iztekom. Port 80 mora ostati odprt (HTTP challenge). Ni potrebnih ročnih posegov.

---

### 5B. Linux strežnik – Nginx reverse proxy

#### Namestitev

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

#### Nginx konfiguracija

Ustvarite `/etc/nginx/sites-available/clanstvo`:

```nginx
server {
    listen 80;
    server_name clanstvo.vasadomena.si;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name clanstvo.vasadomena.si;

    ssl_certificate     /etc/letsencrypt/live/clanstvo.vasadomena.si/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/clanstvo.vasadomena.si/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    # HSTS – brskalnik vedno uporablja HTTPS za to domeno
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Omejitev velikosti uploadov (skladno z MAX_UPLOAD_BYTES v aplikaciji)
    client_max_body_size 12M;

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/clanstvo /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

#### Let's Encrypt certifikat

```bash
sudo certbot --nginx -d clanstvo.vasadomena.si
```

Certbot samodejno nastavi certifikat in obnovo. Preverite timer:

```bash
sudo systemctl status certbot.timer
```

---

## 6. Vzdrževanje

### Ročni backup baze podatkov

Baza je na `./data/clanstvo.db`. Kopirajte jo na varno lokacijo:

```bash
# Lokalni backup z datumom
cp data/clanstvo.db backups/clanstvo_$(date +%Y%m%d).db

# Backup na oddaljeni strežnik (primer z rsync)
rsync -az data/clanstvo.db user@backup-server:/backup/radioklub/
```

### Samodejni backup (cron)

```bash
# Dodajte v crontab (crontab -e):
# Dnevni backup ob 2:00
0 2 * * * cp /opt/radioklub/data/clanstvo.db /backup/clanstvo_$(date +\%Y\%m\%d).db

# Brisanje backupov starejših od 30 dni
0 3 * * * find /backup/ -name "clanstvo_*.db" -mtime +30 -delete
```

### Čiščenje Docker virov

```bash
# Odstranite neuporabljene plasti in vsebniki
docker system prune -f

# Pregled prostora
docker system df
```

### Pregled zdravja vsebnika

```bash
docker compose ps       # STATUS: healthy
docker compose logs -f  # sledenje logom v živo
```

### Pregled audit loga direktno v SQLite

```bash
# Zadnjih 20 akcij
sqlite3 data/clanstvo.db \
  "SELECT datetime(cas,'localtime'), uporabnik, akcija, opis \
   FROM audit_log ORDER BY cas DESC LIMIT 20;"

# Neuspešne prijave
sqlite3 data/clanstvo.db \
  "SELECT datetime(cas,'localtime'), uporabnik, ip \
   FROM audit_log WHERE akcija='login_fail' ORDER BY cas DESC LIMIT 20;"
```

---

## 7. Posodobitev aplikacije

```bash
cd /opt/radioklub-clanstvo

# 1. Naredite backup baze pred posodobitvijo
cp data/clanstvo.db backups/clanstvo_pred_posod_$(date +%Y%m%d).db

# 2. Prenesite nov image in zaženite
docker compose pull
docker compose up -d

# 3. Preverite
docker compose ps
docker compose logs --tail=20
```

> Nov Docker image je samodejno zgrajen in objavljen ob vsaki posodobitvi kode. Lokalni build ni potreben.

Migracije baze se izvedejo samodejno ob zagonu (funkcija `_migriraj_bazo()` v `main.py`). **Podatki v `./data/` se ob posodobitvi ne izbrišejo.**

---

## 8. CI/CD – GitHub Actions in Container Registry

### Pregled

Vsak push na vejo `main` samodejno sproži GitHub Actions workflow (`.github/workflows/docker-publish.yml`), ki:

1. Zgradi Docker image za **linux/amd64** in **linux/arm64** (Raspberry Pi)
2. Potisne image v **GitHub Container Registry (GHCR)**: `ghcr.io/s56oa/radioklubupravljanjeclanstva`
3. Označi image z `latest` (za `main` vejo) in verzijsko oznako (za git tage `v*`)

Workflow za avtentikacijo v GHCR uporablja samodejni `secrets.GITHUB_TOKEN` – **ni potrebnih dodatnih skrivnosti ali konfiguracije**.

### Verzioniranje

| Trigger | Docker tag |
|---------|-----------|
| Push na `main` | `latest`, `main` |
| Git tag `v1.12` | `1.12`, `1`, `latest` |

Za izdajo nove verzije zadostuje:
```bash
git tag v1.13
git push origin v1.13
```

### Prednosti za končne uporabnike

Ker je image vnaprej zgrajen, **kloniranje repozitorija in lokalni build nista potrebna**. Uporabnik potrebuje samo:

```bash
# 1. Prenesite docker-compose.yml in .env.example
curl -fsSL https://raw.githubusercontent.com/s56oa/RadioklubUpravljanjeClanstva/main/docker-compose.yml -o docker-compose.yml
curl -fsSL https://raw.githubusercontent.com/s56oa/RadioklubUpravljanjeClanstva/main/.env.example -o .env

# 2. Uredite .env (SECRET_KEY in ADMIN_GESLO)

# 3. Zaženite – Docker image se samodejno prenese
docker compose up -d
```

### Posodobitev na novo verzijo

```bash
docker compose pull   # prenese novo verzijo image-a
docker compose up -d  # zažene nov vsebnik
```

### Pregled zgrajenih image-ov

Dostopno na: `https://github.com/s56oa/RadioklubUpravljanjeClanstva/pkgs/container/radioklubupravljanjeclanstva`

### Workflow datoteka

```
.github/
└── workflows/
    └── docker-publish.yml    ← CI/CD definicija
```

Ključne nastavitve workflowa:

| Nastavitev | Vrednost |
|-----------|---------|
| Platforme | `linux/amd64`, `linux/arm64` |
| Registry | `ghcr.io` |
| Cache | GitHub Actions cache (`type=gha`) |
| Avtentikacija | `secrets.GITHUB_TOKEN` (samodejno) |

---

## 9. Lokalni razvoj brez Dockerja (za razvijalce)

Za razvoj in testiranje:

```bash
# Ustvari virtualno okolje
python3 -m venv venv
source venv/bin/activate   # Linux/Mac
# ali: venv\Scripts\activate  (Windows)

# Namesti odvisnosti
pip install -r requirements.txt
pip install -r requirements-dev.txt   # za teste

# Nastavi spremenljivki okolja
export SECRET_KEY="dev-kljuc-samo-za-razvoj"
export ADMIN_GESLO="DevGeslo123!"

# Zaženi razvojni strežnik
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Aplikacija je dostopna na `http://localhost:8000`. Zastavica `--reload` samodejno znova naloži kodo ob vsaki spremembi datoteke.

### Zagon testov

```bash
pytest tests/ -v
```

Vsi testi (34) uporabljajo SQLite v pomnilniku – ne pišejo v `data/clanstvo.db`.

---

## 10. Arhitektura podatkovnega modela

### Tabele

```
clani
├── id (PK)
├── priimek, ime
├── klicni_znak (indexed)
├── naslov_ulica, naslov_posta
├── tip_clanstva, operaterski_razred
├── mobilni_telefon, telefon_doma, elektronska_posta
├── soglasje_op, izjava
├── veljavnost_rd (Date)
├── es_stevilka
├── aktiven (Bool)
├── opombe
├── created_at, updated_at
│
├── clanarine (1:N)
│   ├── clan_id (FK)
│   ├── leto (Int)
│   ├── datum_placila (Date, nullable)
│   ├── znesek (Text, nullable)
│   └── opombe
│
├── aktivnosti (1:N)
│   ├── clan_id (FK)
│   ├── leto (Int)
│   ├── datum (Date, nullable)
│   ├── opis (String 1000)
│   └── delovne_ure (Float, nullable)
│
└── skupine (M:N prek clan_skupina)
    ├── clan_id (FK)
    └── skupina_id (FK)

skupine
├── id (PK)
├── ime
└── opis

uporabniki
├── id (PK)
├── uporabnisko_ime (unique, indexed)
├── geslo_hash (bcrypt)
├── vloga (admin/urednik/bralec)
├── ime_priimek
├── aktiven
├── totp_skrivnost (Text, nullable)   ← base32 TOTP secret (v1.12)
├── totp_aktiven (Bool, default False) ← ali je 2FA aktivirana (v1.12)
└── created_at

nastavitve
├── kljuc (PK)
├── vrednost
└── opis

audit_log
├── id (PK)
├── cas (DateTime, indexed)
├── uporabnik
├── ip
├── akcija (String, indexed)
└── opis
```

### Migracije

Aplikacija ne uporablja Alembic. Ročne migracije so implementirane v `app/main.py → _migriraj_bazo()` in se izvedejo ob vsakem zagonu. Migracija z `ALTER TABLE` se izvede samo, če stolpec še ne obstaja.

Nove tabele ustvari `Base.metadata.create_all(bind=engine)` samodejno.

### KlubContextMiddleware

`KlubContextMiddleware` (v `main.py`) se izvede pri vsaki zahtevi in prebere `klub_oznaka` ter `klub_ime` iz tabele `nastavitve`. Vrednosti se shranijo v `request.state` in so dostopne v vseh Jinja2 predlogah prek `request.state.klub_oznaka` oz. `request.state.klub_ime`. Navigacijska vrstica in naslov strani (`<title>`) sta tako dinamična in odražata nastavitve kluba brez ponovnega zagona aplikacije.

### Login tok z 2FA

Ko ima uporabnik aktivirano dvostopenjsko avtentikacijo, je potek prijave dvostopenjski:

```
POST /login (geslo OK, totp_aktiven=True)
   → session["_2fa_cakanje"] = uporabnisko_ime
   → redirect GET /login/2fa

POST /login/2fa (koda)
   → pyotp.TOTP(skrivnost).verify(koda, valid_window=1)
   → OK: session["uporabnik"] = {...}  → redirect /clani
   → FAIL: rate limit incr, log login_2fa_napaka, vrni stran z napako
```

Aktivacija poteka prek `/profil/2fa-nastavi` (GET: generiraj QR SVG, POST `/profil/2fa-potrdi`: shrani skrivnost šele po uspešni verifikaciji). Onemogočanje zahteva veljavno OTP kodo (`POST /profil/2fa-onemogoči`).

Audit log akcije v zvezi z 2FA:

| Akcija | Opis |
|--------|------|
| `login_2fa_caka` | Geslo pravilno, čakanje na OTP kodo |
| `login_2fa_napaka` | Napačna OTP koda pri prijavi |
| `2fa_aktivirana` | Uporabnik je aktiviral 2FA |
| `2fa_onemogocena` | Uporabnik je onemogočil 2FA |

---

## 11. Varnostne opombe

Podroben varnostni pregled je v datoteki `Varnost.md`.

### Kritično pred prvim zagonom

1. **Nastaviti `SECRET_KEY`** v `.env` – brez tega so session piškotki podpisani s predvidljivim nizom.
2. **Nastaviti `ADMIN_GESLO`** v `.env` – privzeto geslo `admin123` je splošno znano.
3. **Po prijavi takoj zamenjati geslo** prek Admin → Moj profil.

### Implementirani ukrepi

| Ukrep | Različica |
|-------|-----------|
| bcrypt hashiranje gesel | v1.0 |
| Vloge in avtorizacija | v1.0 |
| XSS zaščita (Jinja2 auto-escape) | v1.0 |
| SQL injection zaščita (SQLAlchemy ORM) | v1.0 |
| Security headers (X-Frame, X-Content-Type, itd.) | v1.2 |
| Session hardening (SameSite=Strict, 1h timeout) | v1.2 |
| Rate limiting prijave (10 / 15 min per IP) | v1.2 |
| Omejitev nalaganja datotek (10 MB, samo .xlsx) | v1.2 |
| CSRF token zaščita na vseh POST endpointih | v1.3 |
| Politika gesel (14+ znakov, mixed case + digit + special) | v1.3 |
| Normalizacija vhodnih podatkov | v1.7 |
| Allowlist za tip članstva | v1.7 |
| Audit log | v1.7 |
| Predogled uvoza (2-koračni tok) | v1.8 |
| CSRF + Session temp datoteke za uvoz | v1.8 |
| TOTP dvostopenjska avtentikacija (opcijska) | v1.12 |

### Varnostno vzdrževanje

```bash
# Preverjanje ranljivosti v odvisnostih
pip install pip-audit
pip-audit -r requirements.txt
```

---

## 12. Testi

Testi se nahajajo v mapi `tests/` in za zagon zahtevajo `requirements-dev.txt`.

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

### Testne datoteke

| Datoteka | Področje | Testov |
|----------|----------|--------|
| `test_auth.py` | hash/preveri geslo, zahteve gesla, vloge | 11 |
| `test_csrf.py` | CSRF token, csrf_protect dependency | 5 |
| `test_normalizacija.py` | _normaliziraj_clan (title case, KZ, email) | 6 |
| `test_config.py` | get_nastavitev, get_seznam, get_tipi_clanstva | 4 |
| `test_audit.py` | log_akcija, napaka ne propagira | 3 |
| `test_routes.py` | GET/POST /login, /health, /clani redirect | 5 |
| **Skupaj** | | **34** |

### Testna infrastruktura

`tests/conftest.py` ustvari:
- `engine` fixture – SQLite `/:memory:` z `StaticPool` (deljeno med sesjami)
- `db` fixture – SQLAlchemy seja na testnem engine
- `client` fixture – FastAPI `TestClient` z dependency override za `get_db`

Testi ne pišejo v `data/clanstvo.db`. Vsak test dobi svežo bazo.

---

*Radio klub Člani – tehnična dokumentacija, različica 1.12 + CI/CD*
