# Radio klub Člani – Upravljanje Članstva

Spletna aplikacija za upravljanje podatkov o članstvu radiokluba.
Deluje v brskalniku, gostuje na Synology NAS, Linux strežniku ali Raspberry Pi z Docker.

![Docker Image](https://github.com/s56oa/RadioklubUpravljanjeClanstva/actions/workflows/docker-publish.yml/badge.svg)

---

## Hitra namestitev (2 koraka)

Ne potrebujete klonirati repozitorija. Dovolj sta **dve datoteki**.

### 1. Prenesite konfiguracijski datoteki

```bash
mkdir radioklub-clanstvo && cd radioklub-clanstvo

# docker-compose.yml
curl -fsSL https://raw.githubusercontent.com/s56oa/RadioklubUpravljanjeClanstva/main/docker-compose.yml -o docker-compose.yml

# .env predloga
curl -fsSL https://raw.githubusercontent.com/s56oa/RadioklubUpravljanjeClanstva/main/.env.example -o .env
```

### 2. Nastavite `.env` in zaženite

Uredite `.env` (obvezno samo prvi dve vrstici):

```ini
SECRET_KEY=<generirajte: python3 -c "import secrets; print(secrets.token_urlsafe(32))">
ADMIN_GESLO=<varno-geslo>
OKOLJE=produkcija
```

```bash
mkdir -p data && chmod 777 data
docker compose up -d
```

Aplikacija je dostopna na: **http://localhost:8000**

Privzeti admin: `admin` / geslo iz `ADMIN_GESLO`. **Takoj po prijavi zamenjajte geslo!**

> Docker image se samodejno prenese iz GitHub Container Registry – gradnja ni potrebna.

---

## Posodobitev

```bash
docker compose pull && docker compose up -d
```

Podatki v `./data/` ostanejo nespremenjeni. Migracije baze se izvedejo samodejno.

---

## Dokumentacija

| Dokument | Vsebina |
|----------|---------|
| **[Uporabniski-prirocnik.md](Uporabniski-prirocnik.md)** | Navodila za vse vloge: iskanje, vnos, plačila, aktivnosti, uvoz/izvoz |
| **[Tehnicna-dokumentacija.md](Tehnicna-dokumentacija.md)** | Namestitev z Docker, konfiguracija, HTTPS, vzdrževanje, arhitektura |
| **[Varnost.md](Varnost.md)** | Varnostni pregled, odprte ranljivosti, GDPR |
| **[Izboljsave.md](Izboljsave.md)** | Backlog funkcionalnosti in razvoj po različicah |

---

## Vloge uporabnikov

| Vloga | Opis |
|-------|------|
| **admin** | Polni dostop: člani, uporabniki, nastavitve, uvoz/izvoz, audit log |
| **urednik** | Dodaj/uredi člane, beleži plačila in aktivnosti, izvoz |
| **bralec** | Samo ogled |

Vsi uporabniki lahko prek **Moj profil** aktivirajo opcijsko **dvostopenjsko avtentikacijo (TOTP)** – Google Authenticator, Aegis ali katera koli TOTP aplikacija.

---

## Podprte platforme

- Linux x64 (Ubuntu, Debian, …)
- Raspberry Pi 3B+ / 4 / 5 (ARM64)
- Mac z Apple Silicon (M1/M2/M3)
- Synology NAS Intel (DSM 7.2+, Container Manager)

Podrobna navodila za vsako platformo: **[Tehnicna-dokumentacija.md](Tehnicna-dokumentacija.md)**

---

## Razvoj in lokalni build

```bash
git clone https://github.com/s56oa/RadioklubUpravljanjeClanstva.git
cd RadioklubUpravljanjeClanstva

# V docker-compose.yml zamenjaj vrstico image: z: build: .
docker compose up -d --build
```

Za zagon testov:

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```
