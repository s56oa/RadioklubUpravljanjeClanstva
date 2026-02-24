# Varnostni pregled – S59DGO Upravljanje Članstva

*Datum pregleda: 2026-02-23 | Posodobljeno: 2026-02-24 (v1.12)*

---

## Povzetek

Aplikacija je primarna za uporabo v zaupljivem lokalnem okolju (radioklub, domače omrežje, VPN).
Od različice v1.3 so bile odpravljene CSRF zaščita, politika gesel, validacija vhodnih podatkov in implementirana tako audit log kot opcijska TOTP dvostopenjska avtentikacija (v1.12). Preostajata dve **kritični** konfiguraciji (`SECRET_KEY`, admin geslo), ki ju je treba nastaviti pred vsakim zagonom.

---

## Implementirani varnostni ukrepi

| Ukrep | Status | Različica |
|---|---|---|
| bcrypt hashiranje gesel | ✅ | v1.0 |
| Vloge in avtorizacija (admin/urednik/bralec) | ✅ | v1.0 |
| Varnostni HTTP headers | ✅ | v1.2 |
| Session SameSite=Strict, timeout 1h | ✅ | v1.2 |
| Session fixation preprečevanje | ✅ | v1.2 |
| Rate limiting prijave (10 / 15 min per IP) | ✅ | v1.2 |
| Timing attack mitigacija pri prijavi | ✅ | v1.2 |
| Omejitev nalaganja datotek (10 MB, .xlsx) | ✅ | v1.2 |
| Docker port samo localhost (127.0.0.1) | ✅ | v1.2 |
| Preprečevanje brisanja lastnega računa (admin) | ✅ | v1.2 |
| CSRF token zaščita na vseh POST endpointih | ✅ | v1.3 |
| Politika gesel (14+ znakov, mixed case, digit, special) | ✅ | v1.3 |
| Preverjanje starega gesla pri spremembi | ✅ | v1.3 |
| Normalizacija vhodnih podatkov (title case, uppercase KZ) | ✅ | v1.7 |
| Validacija formata e-pošte | ✅ | v1.7 |
| Allowlist za tip članstva | ✅ | v1.7 |
| Audit log (prijave, ogledi, CRUD, izvozi) | ✅ | v1.7 |
| TOTP dvostopenjska avtentikacija (opcijska, RFC 6238) | ✅ | v1.12 |
| XSS – Jinja2 auto-escape (`\| safe` samo za interni SVG QR) | ✅ | v1.0 |
| SQL injection – SQLAlchemy ORM, parameterized queries | ✅ | v1.0 |

---

## Odprte ranljivosti – po prioriteti

### KRITIČNO

#### K1. Šibak privzeti `SECRET_KEY`
- **Datoteka:** `app/main.py` vrstica 142, `docker-compose.yml` vrstica 10
- **Tveganje:** Če `SECRET_KEY` ni nastavljen v `.env`, session cookie podpiše s predvidljivim nizom
  `s59dgo-zamenjajte-v-produkciji` → napadalec lahko ponaredil sejno piškotico in prevzame katerikoli račun.
- **Ukrep:** **OBVEZNO** pred prvim zagonom ustvari in nastavi vrednost:
  ```bash
  python3 -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
  Shranjeno v `.env` → `SECRET_KEY=<generirani_niz>`

#### K2. Privzeto geslo admina
- **Datoteka:** `docker-compose.yml` vrstica 11 → `ADMIN_GESLO=admin123`
- **Tveganje:** Trivialno geslo, splošno znano vsem ki so videli repozitorij.
- **Ukrep:** **TAKOJ** po namestitvi zamenjaj prek Admin → Uporabniki → Uredi → Novo geslo.

---

### VISOKO

#### V1. Brez HTTPS
- **Tveganje:** Session cookie in gesla se prenašajo v čistem tekstu (pasivno prisluškovanje).
- **Ukrep:** Nginx reverse proxy z Let's Encrypt certifikatom. Po namestitvi v `main.py` nastavi
  `https_only=True` (vrstica 145) in dodaj `Strict-Transport-Security` header v `SecurityHeadersMiddleware`.
  ```nginx
  server {
      listen 443 ssl;
      server_name clanstvo.vasadomena.si;
      ssl_certificate /etc/letsencrypt/live/.../fullchain.pem;
      ssl_certificate_key /etc/letsencrypt/live/.../privkey.pem;
      location / { proxy_pass http://127.0.0.1:8000; }
  }
  ```

#### V2. ~~Šibka politika gesel~~ ✅ IMPLEMENTIRANO (v1.3)
- `preveri_zahteve_gesla()` v `app/auth.py`: min. 14 znakov, mali/veliki znaki, številka, posebni znak.

#### V3. Rate limiting ni trajen
- **Datoteka:** `app/main.py` – `_login_attempts` dict (vrstice 38–71)
- **Tveganje:** Ob ponovnem zagonu strežnika se števec resetira. Napadalec, ki pozna urnik restartov,
  dobi periodično "svežo" okno za brute-force.
- **Ukrep:** Shraniti neuspele poskuse v SQLite tabelo `login_attempts` (cas, ip) namesto v-memory dict.

---

### SREDNJE

#### S1. ~~Audit log manjka~~ ✅ IMPLEMENTIRANO (v1.7)
- Nova tabela `audit_log` beleži: prijave (uspešne/neuspešne), odjave, ogled člana, CRUD nad člani, izvozi.
- Admin pregled na `/audit` z filtrom po tipu akcije in izvozom v Excel.

#### S2. SQLite ni primeren za večje sočasne obremenitve
- **Tveganje:** Pri >10 sočasnih pisanjih možni `database is locked` napake.
- **Ukrep:** Za produkcijsko rabo (>50 sočasnih uporabnikov) migracija na PostgreSQL.

#### S3. Ni omejitve velikosti za navadne POST zahteve
- **Datoteka:** `app/main.py` – manjka `ContentSizeLimitMiddleware`
- **Tveganje:** Napadalec z veljavno sejo pošlje izjemno velik POST body (npr. v polju `opombe`),
  kar obremeni spomin procesorja/RAM.
- **Ukrep:**
  ```python
  from starlette.middleware.trustedhost import TrustedHostMiddleware
  # ali omejitev prek Nginx: client_max_body_size 1m;
  ```

#### S4. Ni izteka seje ob neaktivnosti
- **Tveganje:** Seja ostane veljavna 1 uro od prijave ne glede na aktivnost. Zapuščena seja
  na skupnem računalniku ostane dostopna do 60 minut.
- **Ukrep:** Middleware ki beleži čas zadnje aktivnosti in preusmeri na `/logout` po 30 minutah
  brez zahtev.

#### S5. `vloga` ni validirana na dovoljene vrednosti
- **Datoteka:** `app/routers/uporabniki.py` vrstice 73, 177
- **Tveganje:** Admin lahko nastavi arbitrary niz za `vloga` (npr. `"superadmin"`). Funkciji
  `is_admin()` in `is_editor()` sta robustni (preverjata točni niz), zato bi taka vloga dobila
  le bralčeve pravice – funkcionalnih posledic ni. Operativna zmeda je možna.
- **Ukrep:** Dodati validacijo: `if vloga not in VLOGE: vloga = "bralec"` v oba POST handlerja.

#### S6. Skupiny brisanje dovoli urednik, ne samo admin
- **Datoteka:** `app/routers/skupine.py` vrstica 143
- **Opomba:** `POST /{skupid}/izbrisi` zahteva `is_editor`, medtem ko brisanje članov zahteva
  `is_admin`. Nedoslednost: urednik lahko izbriše skupino (z vsemi asociacijami), a ne more
  izbrisati člana. Verjetno je to nameravano vedenje, a vredno preveriti.
- **Ukrep:** Odločiti ali brisanje skupin zahteva admin vlogo (konzistentno z brisanjem clanov).

---

### NIZKO

#### N1. `require_role` referenca na neobstoječ template
- **Datoteka:** `app/auth.py` vrstica 51
- **Tveganje:** Funkcija `require_role()` referira `"403.html"`, ki ne obstaja v `app/templates/`.
  Če bi bila ta funkcija kdaj klicana z nezadostnimi pravicami, bi povzročila 500 namesto 403.
  Funkcija v trenutni kodi **ni klicana nikjer** (vsi routerji uporabljajo `require_login` +
  `is_admin`/`is_editor` ročno) – mrtva koda.
- **Ukrep:** Ustvari `app/templates/403.html` ali odstrani `require_role` funkcijo.

#### N2. Audit log raste brez omejitev
- **Datoteka:** `app/models.py`, `app/routers/audit.py`
- **Tveganje:** Vsak ogled člana ustvari vpis v `audit_log`. Pri intenzivni rabi (npr. serijsko
  brskanje) tabela hitro naraste; pri 1 GB diskovnega prostora in 1 KB/vpis to pomeni ~1 milijon
  vpisov preden nastane problem.
- **Ukrep:** Periodično čiščenje starejših vpisov (npr. starejših od 1 leta) prek cron/Docker timer.

#### N3. HSTS header manjka (ko bo HTTPS aktiviran)
- **Datoteka:** `app/main.py` – `SecurityHeadersMiddleware` (vrstice 47–55)
- **Ukrep:** Po aktivaciji HTTPS dodaj:
  ```python
  response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
  ```

#### N4. Začasno geslo ne ustreza politiki
- **Datoteka:** `app/routers/uporabniki.py` – `_generiraj_geslo(12)` (vrstice 15–20)
- **Opomba:** Generirano začasno geslo je 12 znakov in vsebuje samo alfanumerične znake, kar ne
  ustreza politiki (14 znakov, special char). Geslo je namenjeno takojšnji zamenjavi in ni
  problematično, a povzroča operativno zmedo ker admin ne more "preveriti" moči začasnega gesla.
- **Ukrep:** Podaljšati na 16 znakov in dodati posebne znake; ali dokumentirati da ta gesla so
  zunaj domene politike.

#### N5. Dependencies brez hash validacije
- **Tveganje:** `requirements.txt` fiksira verzije, a brez `--hash` → napad na supply chain
  z zamenjavo paketa ostane neodkrit.
- **Ukrep:** Redno zagnati `pip-audit` za preverjanje znanih ranljivosti:
  ```bash
  pip install pip-audit && pip-audit -r requirements.txt
  ```

#### N6. SQLite backup brez transakcijskega varovanja
- **Datoteka:** `app/routers/izvoz.py` – `backup_db` (vrstica 253)
- **Tveganje:** Backup se opravi s prenosom live datoteke medtem ko je baza aktivna. Pri privzetem
  SQLite journal načinu (`DELETE`) je to varno, pri `WAL` načinu pa bi bila potrebna `VACUUM INTO`.
- **Ukrep:** Sprejemljivo za obseg te aplikacije; ob morebitni migraciji na WAL posodobi logiko.

---

## GDPR opombe

Aplikacija obdeluje osebne podatke članov (ime, naslov, telefon, e-pošta).

| Zahteva | Status | Opomba |
|---|---|---|
| Beleženje soglasja | ⚠️ Delno | Polje `soglasje_op` obstaja, ni formalne potrditvene procedure |
| Pravica do pozabe | ⚠️ Delno | Brisanje je trajno (cascade delete), brez mehkega brisanja ali izvajalnih jamstev |
| Izvoz podatkov (GDPR čl. 20) | ✅ | Excel backup vsebuje vse podatke za posameznega člana |
| Omejitev dostopa | ✅ | Vloge admin/urednik/bralec; bralec ne more pisati |
| Šifriranje v prenosu | ❌ | Brez HTTPS (glej V1) |
| Beleženje dostopa | ✅ v1.7 | Audit log beleži vsak ogled in spremembo podatkov |
| Minimizacija podatkov | ✅ | Zbira samo polja, ki jih ZRS zahteva |

---

## Povzetek stanja po različicah

| Različica | Varnostne spremembe |
|---|---|
| v1.0 | bcrypt, vloge, osnovna avtorizacija |
| v1.2 | Security headers, rate limiting, session hardening, file upload limits |
| v1.3 | CSRF zaščita, politika gesel, profil/sprememba gesla |
| v1.7 | Audit log, validacija e-pošte, normalizacija vhodnih podatkov, allowlist tipov |
| v1.12 | Opcijska TOTP 2FA (pyotp, RFC 6238); skrivnost shranjena šele po verifikaciji; rate limiting reuse |

---

## Priporočen vrstni red odprave

1. **Pred vsakim zagonom:** Nastaviti `SECRET_KEY` in `ADMIN_GESLO` v `.env` (K1, K2)
2. **Pred javnim dostopom:** Dodati HTTPS z Nginx + Let's Encrypt (V1)
3. **Priporočeno za vse uporabniške račune:** Aktivirati 2FA prek Moj profil → Aktiviraj 2FA (posebej za admin)
4. **V kratkem:** Validacija `vloga` polja pri urejanju uporabnikov (S5)
5. **Priporočeno:** Trajen rate limiting v SQLite (V3); inaktivni session timeout (S4)
6. **Operativno:** Redni `pip-audit`; periodično čiščenje audit loga (N2, N5)

---

## Orodja za varnostno vzdrževanje

```bash
# Preverjanje ranljivosti v odvisnostih
pip install pip-audit
pip-audit -r requirements.txt

# Generiranje varnega SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Pregled audit loga (zadnjih 50 vpisov) direktno v SQLite
sqlite3 data/clanstvo.db "SELECT cas, uporabnik, akcija, opis FROM audit_log ORDER BY cas DESC LIMIT 50;"

# Pregled neuspešnih prijav
sqlite3 data/clanstvo.db "SELECT cas, uporabnik, ip, opis FROM audit_log WHERE akcija='login_fail' ORDER BY cas DESC LIMIT 20;"

# Pregled neuspešnih 2FA poskusov
sqlite3 data/clanstvo.db "SELECT cas, uporabnik, ip FROM audit_log WHERE akcija='login_2fa_napaka' ORDER BY cas DESC LIMIT 20;"

# Kdo ima aktivirano 2FA
sqlite3 data/clanstvo.db "SELECT uporabnisko_ime, vloga FROM uporabniki WHERE totp_aktiven=1 AND aktiven=1;"
```
