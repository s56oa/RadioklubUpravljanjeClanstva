# Radio klub Člani – Upravljanje Članstva

Spletna aplikacija za upravljanje podatkov o članstvu radiokluba.
Deluje v brskalniku, gostuje na Synology NAS, Linux strežniku ali Raspberry Pi z Docker.

---

## Dokumentacija

| Dokument | Vsebina |
|----------|---------|
| **[Uporabniski-prirocnik.md](Uporabniski-prirocnik.md)** | Navodila za vse vloge: iskanje, vnos, plačila, aktivnosti, uvoz/izvoz |
| **[Tehnicna-dokumentacija.md](Tehnicna-dokumentacija.md)** | Namestitev z Docker, konfiguracija, HTTPS, vzdrževanje, arhitektura |
| **[Varnost.md](Varnost.md)** | Varnostni pregled, odprte ranljivosti, GDPR |
| **[Izboljsave.md](Izboljsave.md)** | Backlog funkcionalnosti in razvoj po različicah |

---

## Hitra namestitev (Docker)

### 1. Pridobite kodo

```bash
git clone <url-repozitorija> radioklub-clanstvo
cd radioklub-clanstvo
```

### 2. Nastavite konfiguracijsko datoteko

```bash
cp .env.example .env
```

Uredite `.env`:

```ini
SECRET_KEY=<dolg-naključni-niz>    # python3 -c "import secrets; print(secrets.token_urlsafe(32))"
ADMIN_GESLO=<varno-geslo>
OKOLJE=produkcija
```

### 3. Zaženite

```bash
docker compose up -d --build
```

Aplikacija je dostopna na: **http://localhost:8000**

### 4. Privzeti admin

- Uporabniško ime: `admin`
- Geslo: vrednost `ADMIN_GESLO` iz `.env`

> **Takoj po prvi prijavi zamenjajte geslo prek Admin → Moj profil!**

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

## Posodobitev

```bash
# Backup pred posodobitvijo
cp data/clanstvo.db backups/clanstvo_$(date +%Y%m%d).db

# Posodobi kodo in znova zgradi
git pull
docker compose up -d --build
```

Podatki v `./data/` ostanejo nespremenjeni. Migracije baze se izvedejo samodejno.
