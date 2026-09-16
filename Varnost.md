# Varnostni pregled – S59DGO Upravljanje Članstva

*Datum pregleda: 2026-02-23 | Posodobljeno: 2026-09-17 (v1.29)*

---

## Povzetek

Aplikacija je primarna za uporabo v zaupljivem lokalnem okolju (radioklub, domače omrežje, VPN).
Od različice v1.3 so bile odpravljene CSRF zaščita, politika gesel, validacija vhodnih podatkov in implementirana tako audit log kot opcijska TOTP dvostopenjska avtentikacija (v1.12). V v1.13 so bile dodane varnostne izboljšave (persistentni rate limiting, omejitev POST zahtevkov, iztok seje ob neaktivnosti). V v1.14 so bili dodani novi pregledi (aktivnosti, plačila, dashboard) brez novih varnostnih tveganj. V v1.16 je bil odstranjen debug endpoint za UPN QR in odpravljena ranljivost pri HTTP Content-Disposition headerju z non-ASCII znaki. V v1.18 je bila odpravljena ranljivost za email header injection (strip `\r\n` iz zadeve/naslovov) in Jinja2 email predloge zaščitene z `SandboxedEnvironment` (preprečitev template injection). V v1.19 so bile odpravljene tri varnostne pomanjkljivosti: backup Excel omejen na admin, IDOR zaščita pri brisanju članarine in validacija formata vhodnih podatkov. V v1.20 so bile izvedene štiri varnostne izboljšave: opozorilo za SMTP "plain" način v UI, generično SMTP napako sporočilo, `data-geslo` namesto inline JS pri kopiranju gesla in popravek dolžine resetiranega gesla (12 → 16 znakov). V v1.21 je bil opravljen celovit varnostni pregled: odpravljene IDOR ranljivosti pri vlogah in aktivnostih (`clan_id` validacija v uredi+izbrisi endpointih), popravljena logika filtra neplačnikov (manjkajoč pogoj `datum_placila != None`), dodana `try/except ValueError` zaščita pri dodajanju plačil in aktivnosti, razširjena pokritost audit loga na vse CRUD endpointe (vloge, aktivnosti, clanarine, uporabniki), utrjen `ContentSizeLimitMiddleware` (specifične upload poti namesto prefiksa + 411 za manjkajoč `Content-Length` header), čiščenje JSON začasnih datotek AKOS API ob zagonu in refaktoriranje email.py z `_clan_context()` pomočnikom za odpravo podvojene kode. V v1.23 so bili dodani trije varnostni ukrepi pri novi funkciji članske kartice: sanitizacija `Content-Disposition` headerja (klicni znak filtriran na alfanumerične znake z `re.sub`), validacija leta (2000–2100) pri pošiljanju kartice in SMTP pre-check pred generacijo PDF. V v1.24 so bili odpravljeni: DOM XSS v AJAX autocomplete dropdownu za iskanje članov (innerHTML zamenjano z DOM API za vse uporabniške podatke), tiho bulk pošiljanje obvestil kljub izbranemu načinu "Posameznik" (server-side validacija parametra `nacin`), pošiljanje brez obstoja predloge (H5 check) in manjkajoča JS validacija (C2 – disabled gumb). V v1.29 je bil opravljen celovit code + security review: odpravljen shranjeni XSS v JavaScript atributih (`onsubmit`/`onclick` s `confirm()` in interpoliranimi podatki iz baze), uvedena Content-Security-Policy z nonce-om in SRI za CDN vire, validacija sej proti bazi ob vsaki zahtevi, TOTP replay zaščita, SMTP timeout, uveljavljanje tujih ključev v SQLite in nadgradnja odvisnosti (9 Dependabot alertov). Aplikacija se v `OKOLJE=produkcija` s privzetim `SECRET_KEY` ali privzetim `ADMIN_GESLO` (ob prvem zagonu) **ne zažene**.

---

## Implementirani varnostni ukrepi

| Ukrep | Status | Različica |
|---|---|---|
| bcrypt hashiranje gesel | ✅ | v1.0 |
| Vloge in avtorizacija (admin/urednik/bralec) | ✅ | v1.0 |
| Varnostni HTTP headers | ✅ | v1.2 |
| Session SameSite=Strict, timeout 1h, `https_only=False` (namerno) | ✅ | v1.2 |
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
| Zaupljive naprave (SHA-256 hashed token, 30-dnevni httponly cookie) | ✅ | v1.12 |
| IP resolving prek X-Forwarded-For (ProxyHeadersMiddleware) | ✅ | v1.12 |
| Audit log za 2FA in zaupljive naprave | ✅ | v1.12 |
| UPN QR debug endpoint odstranjen (preprečitev razkritja podatkov) | ✅ | v1.16 |
| HTTP Content-Disposition ASCII-safe filename (preprečitev header injection) | ✅ | v1.16 |
| XSS – Jinja2 auto-escape (`\| safe` samo za interni SVG QR) | ✅ | v1.0 |
| SQL injection – SQLAlchemy ORM, parameterized queries | ✅ | v1.0 |
| Persistentni rate limiting (SQLite `login_poskusi`) | ✅ | v1.13 |
| Omejitev velikosti POST zahtevkov (1 MB, `ContentSizeLimitMiddleware`) | ✅ | v1.13 |
| Iztok seje ob neaktivnosti (30 min, `InactivityTimeoutMiddleware`) | ✅ | v1.13 |
| Validacija `vloga` na dovoljene vrednosti pri urejanju uporabnikov | ✅ | v1.13 |
| Začasno geslo ustreza politiki (16 znakov, mešano + posebni) | ✅ | v1.13 |
| Email header injection zaščita (strip `\r\n` iz zadeve, From, To) | ✅ | v1.18 |
| Jinja2 SandboxedEnvironment za email predloge (preprečitev template injection) | ✅ | v1.18 |
| Backup Excel (`/izvoz/backup-excel`) omejen samo na admin (preprečitev dostopa uredniku) | ✅ | v1.19 |
| IDOR zaščita pri brisanju članarine (`clan_id` validacija prepreči brisanje tuje clanarine) | ✅ | v1.19 |
| Validacija formata datuma veljavnosti RD in ES-številke (vrne 200 z napako, ne 500) | ✅ | v1.19 |
| Opozorilo za SMTP "plain" način v nastavitvenem UI (nešifriran prenos) | ✅ | v1.20 |
| Generično SMTP napako sporočilo v UI (podrobnosti samo v app.log, ne uporabniku) | ✅ | v1.20 |
| `data-geslo` atribut namesto inline JS pri kopiranju začasnega gesla | ✅ | v1.20 |
| Reset geslo 12 → 16 znakov (popravek hrošča v reset handlerju, upoštevanje politike) | ✅ | v1.20 |
| Čiščenje `data/tmp/*.xlsx` ob zagonu (zaostale datoteke z osebnimi podatki) | ✅ | v1.20 |
| IDOR zaščita vloge (`clan_id` validacija v uredi + izbrisi endpointih) | ✅ | v1.21 |
| IDOR zaščita aktivnosti (`clan_id` validacija v izbrisi endpointu) | ✅ | v1.21 |
| Popravek filtra neplačnikov – dodan pogoj `datum_placila != None` (odpravlja logično napako: člen z vnosom brez datuma je bil napačno izključen iz neplačnikov) | ✅ | v1.21 |
| `try/except ValueError` za neveljavni datum pri dodajanju plačil in aktivnosti (vrne 200 z napako, ne 500) | ✅ | v1.21 |
| Audit log pokritost: vsi CRUD endpointi (vloge dodaj/izbrisi, aktivnosti dodaj/izbrisi, clanarine dodaj/izbrisi, uporabniki nov/uredi/izbrisi) | ✅ | v1.21 |
| `ContentSizeLimitMiddleware` utrjen: specifične upload poti (`/izvoz/uvozi`, `/izvoz/uvozi-akos`, `/izvoz/uvozi-placila`) namesto prefiksa; 411 za zahteve brez `Content-Length` headerja | ✅ | v1.21 |
| Čiščenje AKOS API JSON začasnih datotek (`data/tmp/akos_api_*.json`) ob zagonu | ✅ | v1.21 |
| `Content-Disposition` filename sanitizacija za PDF kartice (klicni znak filtriran na `[A-Za-z0-9\-]` z `re.sub`, preprečitev header injection) | ✅ | v1.23 |
| Validacija leta (2000–2100) pri `POST /clani/{id}/posli-kartico` (zavrne neveljavne vrednosti) | ✅ | v1.23 |
| SMTP pre-check pred generacijo PDF kartice (ne generira PDF, če SMTP ni konfiguriran – odpravlja nepotrebno računsko delo) | ✅ | v1.23 |
| DOM XSS zaščita v AJAX autocomplete dropdownu – `innerHTML` z user data zamenjano z DOM API (`createElement` + `textContent`) v `prikaziDD()` in `izberClan()` | ✅ | v1.24 |
| Server-side validacija parametra `nacin` pri `POST /obvestila/posli` – prepreči tihi bulk send ko je izbran način "Posameznik" brez veljavnega `clan_id` | ✅ | v1.24 |
| Preverjanje obstoja predloge pred pošiljanjem – `None` predloga vrne flash napako, ne tiho pošiljanje (H5) | ✅ | v1.24 |
| `/clani/iskanje` JSON endpoint zahteva editor+ vlogo (JSONResponse 401/403 brez seje oz. pravic) | ✅ | v1.24 |
| LIKE wildcard escape v iskanju članov – `%` in `_` v iskalnem nizu se escapata (preprečitev nenamerne vrnitvi vseh zapisov) | ✅ | v1.25 |
| Audit log za profil operacije – geslo spremenjeno, 2FA vklop/izklop, odjava zaupljivih naprav zdaj v audit_log | ✅ | v1.25 |
| Audit log za spremembe nastavitev – vse spremembe nastavitev kluba (vključno SMTP) zdaj v audit_log | ✅ | v1.25 |
| Nadgradnja jinja2 3.1.6 – odpravljen sandbox bypass (`\|attr` filter, posredni `str.format`) | ✅ | v1.26 |
| Nadgradnja starlette 0.52.1 – odpravljen Range header parsing DoS + multipart forms DoS | ✅ | v1.26 |
| Nadgradnja python-multipart 0.0.22 – odpravljen path traversal v File filename | ✅ | v1.26 |
| Nadgradnja FastAPI 0.115.6 → 0.135.1 – združljivost s starlette 0.52.1 | ✅ | v1.26 |
| Nadgradnja python-multipart 0.0.22 → 0.0.27 – odpravljen DoS prek prevelikih multipart preambul/epilogov | ✅ | v1.28 |
| Nadgradnja pytest 8.3.4 → 9.0.3 – odpravljena ranljivost tmpdir na UNIX (dev odvisnost) | ✅ | v1.28 |
| CSRF token dodan v obrazec za brisanje uporabnika (`uporabniki/seznam.html`) – popravek hrošča, ki je preprečeval brisanje | ✅ | v1.27 |
| Odjava spremenjena iz GET v POST z CSRF zaščito – preprečuje prisilno odjavo prek `<img src="/logout">` | ✅ | v1.27 |
| Rate limiting razširjen na profil operacije: `/profil/geslo`, `/profil/2fa-potrdi`, `/profil/2fa-onemogoči` | ✅ | v1.27 |
| Per-username rate limiting: `login_poskusi` tabela dobi stolpec `uporabnisko_ime`; zaklepanje velja za IP in račun | ✅ | v1.27 |
| Shranjeni XSS v JS atributih odpravljen: vsi `onsubmit`/`onclick`/`onchange` atributi zamenjani z `data-confirm`/`data-autosubmit`/`data-print` + globalni handler v `base.html` (vrednosti iz baze nikoli ne pridejo v JS kontekst) | ✅ | v1.29 |
| Content-Security-Policy z enkratnim nonce-om (`script-src 'self' 'nonce-…' + CDN`, brez `'unsafe-inline'` za skripte, `object-src 'none'`, `frame-ancestors 'none'`, `form-action 'self'`) | ✅ | v1.29 |
| Subresource Integrity (`integrity="sha384-…" crossorigin="anonymous"`) za vse CDN skripte in stile | ✅ | v1.29 |
| `UserValidationMiddleware`: vsaka zahteva preveri uporabnika proti bazi – deaktiviran/izbrisan uporabnik takoj odjavljen, sprememba vloge takoj velja | ✅ | v1.29 |
| Produkcijske zahteve ob zagonu: `OKOLJE=produkcija` + privzeti/prekratek `SECRET_KEY` (< 32 znakov) ali privzeti `ADMIN_GESLO` ob ustvarjanju admina → aplikacija se ne zažene (`RuntimeError`) | ✅ | v1.29 |
| TOTP replay zaščita: uporabljeni časovni korak shranjen v `uporabniki.totp_zadnji_korak`, ista koda ni ponovno uporabna | ✅ | v1.29 |
| Bcrypt preverjanje tudi za neobstoječega uporabnika (izenačen čas odgovora, ni enumeracije imen) + omejitev dolžine uporabniškega imena (150) | ✅ | v1.29 |
| SMTP `timeout=30` + pošiljanje v threadpoolu (nedosegljiv SMTP ne blokira event loopa) | ✅ | v1.29 |
| Admin ne more spremeniti lastne vloge ali statusa (zaklep zadnjega admina) | ✅ | v1.29 |
| SQLite `PRAGMA foreign_keys=ON` + preverjanje obstoja člana pri dodajanju plačil/aktivnosti/vlog; Alembic 010 počisti osirotele vrstice | ✅ | v1.29 |
| Brisanje skupin samo admin (S9); audit log za reset gesla, skupine CRUD, ZRS/uvoz nastavitve | ✅ | v1.29 |
| `Content-Disposition` sanitizacija za ZRS izvoz (šumniki v oznaki kluba so vračali 500); AKOS klic URL-kodira klicni znak; LIKE escape tudi v `/clani/iskanje` | ✅ | v1.29 |
| SQLite backup prek Online Backup API (konsistenten posnetek, pot iz `DATABASE_URL`) | ✅ | v1.29 |
| Nadgradnja odvisnosti: fastapi 0.141.1, starlette 1.6.0, python-multipart 0.0.32, uvicorn 0.53.0 (Dependabot #9–#17) | ✅ | v1.29 |

---

## Odprte ranljivosti – po prioriteti

### KRITIČNO

#### K1. Šibak privzeti `SECRET_KEY`
- **Datoteka:** `app/main.py` (`_PRIVZETI_SECRET_KEY`, `preveri_produkcijske_nastavitve()`), `docker-compose.yml`
- **Tveganje:** Če `SECRET_KEY` ni nastavljen v `.env`, session cookie podpiše s predvidljivim nizom
  → napadalec lahko ponaredi sejno piškotico in prevzame katerikoli račun.
- **Stanje (v1.29):** V `OKOLJE=produkcija` se aplikacija s privzetim ali prekratkim (< 32 znakov) ključem **ne zažene**;
  `docker-compose.yml` zahteva nastavljen `SECRET_KEY` (`${SECRET_KEY:?…}`). Tveganje ostane le v razvojnem okolju.
- **Ukrep:** **OBVEZNO** pred prvim zagonom ustvari in nastavi vrednost:
  ```bash
  python3 -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
  Shranjeno v `.env` → `SECRET_KEY=<generirani_niz>`

#### K2. Privzeto geslo admina
- **Datoteka:** `docker-compose.yml` → `ADMIN_GESLO=${ADMIN_GESLO:-admin123}`
- **Tveganje:** Trivialno geslo, splošno znano vsem ki so videli repozitorij.
- **Stanje (v1.29):** V `OKOLJE=produkcija` se aplikacija ob **prvem** zagonu (ko admin še ne obstaja) s privzetim geslom ne zažene.
- **Ukrep:** **TAKOJ** po namestitvi zamenjaj prek Admin → Uporabniki → Uredi → Novo geslo.

---

### VISOKO

#### V1. Brez HTTPS (samo pri javnem dostopu)
- **Velja za:** Aplikacije dostopne iz javnega interneta. Za lokalno omrežje ali VPN dostop to tveganje ni relevantno.
- **Tveganje:** Session cookie in gesla se prenašajo v čistem tekstu (pasivno prisluškovanje na javnem omrežju).
- **Ukrep:** HTTPS in HSTS uredite na reverse proxy-u – kode aplikacije ni treba spreminjati.
  - **Synology:** Control Panel → Login Portal → Reverse Proxy → Custom Header → `Strict-Transport-Security: max-age=31536000; includeSubDomains`
  - **Nginx:** `add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;` v server bloku za port 443
- **Opomba glede `https_only`:** `https_only=False` v `SessionMiddleware` (`app/main.py`) ostane **tudi pri javnem HTTPS dostopu**. Nastavitev `https_only=True` bi zlomila dostop za lokalne in VPN uporabnike, ki dostopajo po HTTP. HSTS na reverse proxy-u zagotavlja enako raven zaščite: brskalnik za to domeno nikoli ne pošlje piškotka po HTTP.

#### V2. ~~Šibka politika gesel~~ ✅ IMPLEMENTIRANO (v1.3)
- `preveri_zahteve_gesla()` v `app/auth.py`: min. 14 znakov, mali/veliki znaki, številka, posebni znak.

#### V3. ~~Rate limiting ni trajen~~ ✅ IMPLEMENTIRANO (v1.13, razširjeno v1.27)
- Nova tabela `login_poskusi` (ip, uporabnisko_ime, cas) v SQLite; `check_rate_limit` in `record_failed_attempt` v `app/rate_limit.py`.
- Stari vnosi se samodejno čistijo ob vsakem klicu. Zaklepanje velja za IP **in** username (10 neuspelih v 15 min).
- Alembic migracije `003_login_poskusi.py` in `009_login_poskusi_username.py`.
- Od v1.27 pokrita tudi: sprememba gesla, potrditev 2FA, onemogočanje 2FA.

---

### SREDNJE

#### S1. ~~Audit log manjka~~ ✅ IMPLEMENTIRANO (v1.7)
- Nova tabela `audit_log` beleži: prijave (uspešne/neuspešne), odjave, ogled člana, CRUD nad člani, izvozi.
- Admin pregled na `/audit` z filtrom po tipu akcije in izvozom v Excel.

#### S2. SQLite ni primeren za večje sočasne obremenitve
- **Tveganje:** Pri >10 sočasnih pisanjih možni `database is locked` napake.
- **Ukrep:** Za produkcijsko rabo (>50 sočasnih uporabnikov) migracija na PostgreSQL.

#### S3. ~~Ni omejitve velikosti za navadne POST zahteve~~ ✅ IMPLEMENTIRANO (v1.13, dopolnjeno v1.21)
- `ContentSizeLimitMiddleware` v `app/main.py` – zavrne POST/PUT/PATCH z body > 1 MB (HTTP 413).
- V v1.21 dopolnjeno: namesto izključitve celotnega `/izvoz/` prefiksa so navedene samo specifične upload poti (`/izvoz/uvozi`, `/izvoz/uvozi-akos`, `/izvoz/uvozi-placila`); zahteve brez `Content-Length` headerja prejmejo HTTP 411.

#### S4. ~~Ni izteka seje ob neaktivnosti~~ ✅ IMPLEMENTIRANO (v1.13)
- `InactivityTimeoutMiddleware` v `app/main.py` – odjavi po 30 min neaktivnosti.
- `_last_active` timestamp v seji; ob izteku → `session.clear()` + redirect na `/login?timeout=1`.
- Prijavna stran prikaže obvestilo "Seja je potekla zaradi neaktivnosti."

#### S5. ~~`vloga` ni validirana na dovoljene vrednosti~~ ✅ IMPLEMENTIRANO (v1.13)
- `app/routers/uporabniki.py`: `if vloga not in VLOGE: vloga = "bralec"` v obeh POST handlerjih.

#### S6. ~~Email header injection~~ ✅ IMPLEMENTIRANO (v1.18)
- Strip `\r\n` iz `zadeva`, `From` in `To` polj pred vstavljanjem v SMTP message headers.
- Odpravlja možnost BCC injection in ponarejanje headerjev prek zlonamernih email predlog.

#### S7. ~~Jinja2 template injection v email predlogah~~ ✅ IMPLEMENTIRANO (v1.18)
- `Environment(autoescape=False)` zamenjano z `SandboxedEnvironment(autoescape=False)`.
- `SandboxedEnvironment` omejuje dostop do Python internals (dunder metode, `__class__`, `__mro__`, idr.) in preprečuje izkoriščanje prek user-supplied Jinja2 predlog.
- `autoescape=False` ostane namerno – email predloge vsebujejo HTML s embedded PNG QR kodo.

#### S8. SMTP geslo shranjeno v čistem besedilu v SQLite
- **Datoteka:** `data/clanstvo.db` tabela `nastavitve`, ključ `smtp_geslo`
- **Tveganje:** Kdor ima dostop do SQLite datoteke (backup, direkten dostop do strežnika), vidi SMTP geslo v čistem besedilu.
- **Ukrep:** Priporočamo uporabo **gesla za aplikacijo** (App Password) namesto glavnega računa:
  - Gmail: Varnostne nastavitve → Gesla za aplikacije → Ustvari za *Mail/Drugo*
  - S tem je mogoče kadar koli preklicati dostop samo za to aplikacijo, ne za celoten e-poštni račun.
- **Stanje:** Sprejeto tveganje – šifriranje gesel v bazi zahteva upravljanje šifrirnega ključa, kar je izven obsega te aplikacije.

#### S9. ~~Brisanje skupin dovoli urednik, ne samo admin~~ ✅ IMPLEMENTIRANO (v1.29)
- `POST /skupine/{id}/izbrisi` zahteva `is_admin`; gumb in modal za brisanje vidna samo adminu; audit log `skupina_izbrisana`.

---

### NIZKO

#### N1. ~~`require_role` referenca na neobstoječ template~~ ✅ RAZREŠENO
- `app/templates/403.html` obstaja; `require_role()` ostaja neuporabljena pomožna funkcija.

#### N2. Audit log raste brez omejitev
- **Datoteka:** `app/models.py`, `app/routers/audit.py`
- **Tveganje:** Vsak ogled člana ustvari vpis v `audit_log`. Pri intenzivni rabi (npr. serijsko
  brskanje) tabela hitro naraste; pri 1 GB diskovnega prostora in 1 KB/vpis to pomeni ~1 milijon
  vpisov preden nastane problem.
- **Ukrep:** Periodično čiščenje starejših vpisov (npr. starejših od 1 leta) prek cron/Docker timer.

#### N3. HSTS header (ko je HTTPS aktiviran)
- **Ukrep:** Nastavi na reverse proxy-u – kode aplikacije ni treba spreminjati.
  - Synology: Custom Header v Reverse Proxy nastavitvah
  - Nginx: `add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;`

#### N4. ~~Začasno geslo ne ustreza politiki~~ ✅ IMPLEMENTIRANO (v1.13)
- `_generiraj_geslo(16)` v `app/routers/uporabniki.py`: 16 znakov, mali+veliki+številke+posebni (`!@#$%*-_+?`).
- Garantirano vsaj po en znak iz vsake kategorije (Fisher-Yates mešanje).

#### N5. Dependencies brez hash validacije
- **Tveganje:** `requirements.txt` fiksira verzije, a brez `--hash` → napad na supply chain
  z zamenjavo paketa ostane neodkrit.
- **Ukrep:** Redno zagnati `pip-audit` za preverjanje znanih ranljivosti:
  ```bash
  pip install pip-audit && pip-audit -r requirements.txt
  ```

#### N6. ~~SQLite backup brez transakcijskega varovanja~~ ✅ IMPLEMENTIRANO (v1.29)
- `backup_db` uporablja SQLite Online Backup API (`sqlite3.Connection.backup()`) v začasno datoteko – konsistenten posnetek ne glede na journal način; pot iz `DATABASE_URL`.

#### N7. CDN odvisnost frontenda
- **Datoteka:** `app/templates/base.html`, `dashboard/index.html`, `login*.html`
- **Tveganje:** Bootstrap, jQuery, DataTables in Chart.js se nalagajo s CDN. Kompromis CDN-ja bi pomenil izvajanje tuje kode v aplikaciji.
- **Stanje (v1.29):** Vsi viri imajo SRI (`sha384`) + `crossorigin="anonymous"`; CSP dovoli skripte samo s `'self'`, nonce-om in naštetih CDN domen. Ob nadgradnji CDN verzije je treba preračunati SRI zgoščene vrednosti (`curl -sL <url> | openssl dgst -sha384 -binary | openssl base64 -A`).
- **Ukrep:** Sprejemljivo; alternativa je lokalno gostovanje virov (`app/static/`).

---

## GDPR opombe

Aplikacija obdeluje osebne podatke članov (ime, naslov, telefon, e-pošta).

| Zahteva | Status | Opomba |
|---|---|---|
| Beleženje soglasja | ⚠️ Delno | Polje `soglasje_op` obstaja, ni formalne potrditvene procedure |
| Pravica do pozabe | ⚠️ Delno | Brisanje je trajno (cascade delete), brez mehkega brisanja ali izvajalnih jamstev |
| Izvoz podatkov (GDPR čl. 20) | ✅ | Excel backup vsebuje vse podatke za posameznega člana |
| Omejitev dostopa | ✅ | Vloge admin/urednik/bralec; bralec ne more pisati |
| Šifriranje v prenosu | ⚠️ Pogojno | Lokalno/VPN: ni potrebno. Javni dostop: HTTPS + HSTS na reverse proxy-u (glej V1) |
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
| v1.12 | Opcijska TOTP 2FA (pyotp, RFC 6238); skrivnost shranjena šele po verifikaciji; rate limiting reuse; zaupljive naprave (SHA-256 token, 30 dni); ProxyHeadersMiddleware (pravilni IP v audit logu) |
| v1.13 | Persistentni rate limiting (SQLite); ContentSizeLimitMiddleware (1 MB); InactivityTimeoutMiddleware (30 min); validacija `vloga`; začasno geslo ustreza politiki (16 znakov + posebni) |
| v1.14 | Brez novih varnostnih tveganj; nov /aktivnosti, /clanarine, /dashboard – samo GET, require_login, ORM queries, Jinja2 autoescaping, tojson za Chart.js podatke |
| v1.16 | Odstranjen `/upn/{id}/{leto}/debug` endpoint (razkritje plačilnih podatkov vsem prijavljenim); odpravljena ranljivost `UnicodeEncodeError` → HTTP 500 pri non-ASCII znakih v `Content-Disposition` headerju (ime/priimek člana s šumniki) |
| v1.17 | SMTP geslo shranjeno v čistem besedilu v bazi (sprejeto tveganje S8; priporočena gesla za aplikacijo); dodana `\| safe` zaščita za interni SVG QR; email funkcija brez posebnih varnostnih tveganj |
| v1.18 | Email header injection odpravljena (strip `\r\n` iz zadeve, From, To pred vstavljanjem v headers); Jinja2 `SandboxedEnvironment` za email predloge (preprečitev template injection pri user-supplied Jinja2 predlogah) |
| v1.19 | `/backup-excel` omejen samo na admin; IDOR zaščita pri brisanju članarine (`clan_id` validacija); validacija formata datuma veljavnosti RD in ES-številke pri vnosu/urejanju člana; DB indeksi za `clani.aktiven`, `clanarine.leto`, `aktivnosti.leto` (Alembic 006) |
| v1.20 | Opozorilo za SMTP "plain" način v nastavitvenem UI; generično SMTP napako sporočilo (polna napaka samo v `app.log`); `data-geslo` atribut namesto inline JS `onclick` pri kopiranju začasnega gesla (preprečitev potencialnega JS injection); reset geslo `_generiraj_geslo(12)` → `(16)` (popravek hrošča – reset handler ni upošteval politike min. 14 znakov); čiščenje `data/tmp/*.xlsx` ob zagonu (odstranitev zaostalih datotek z osebnimi podatki) |
| v1.21 | IDOR zaščita vloge (uredi + izbrisi) in aktivnosti (izbrisi) – dodan `clan_id` pogoj v DB poizvedbah; popravek filtra neplačnikov v `/obvestila` (manjkajoč pogoj `datum_placila != None`); `try/except ValueError` pri dodajanju plačil in aktivnosti; razširjena pokritost audit loga (vloge, aktivnosti, clanarine, uporabniki); `ContentSizeLimitMiddleware` utrjen (specifične upload poti + HTTP 411); čiščenje AKOS API JSON tmp datotek ob zagonu; refaktoriranje email.py (`_clan_context()` pomočnik za odpravo podvojene kode) |
| v1.22 | Brez novih varnostnih tveganj; spremembe so UI/UX (date sortiranje v DataTables, dashboard filtri) – brez novih endpointov, brez novih vhodnih podatkov, brez sprememb avtorizacije |
| v1.23 | `Content-Disposition` filename sanitizacija za PDF kartice (klicni znak filtriran na alfanumerične znake); validacija leta (2000–2100) pri pošiljanju kartice; SMTP pre-check pred generacijo PDF (preprečitev nepotrebne CPU porabe) |
| v1.24 | DOM XSS popravek v AJAX autocomplete (`innerHTML` → DOM API); server-side `nacin` validacija v `/obvestila/posli` (preprečitev tihega bulk send); H5 predloga `None` check; `/clani/iskanje` zahteva editor+ vlogo |
| v1.25 | LIKE wildcard escape v iskanju članov; audit log za profil operacije (geslo, 2FA vklop/izklop, odjava naprav); audit log za nastavitve kluba; `KlubContextMiddleware` 60s cache (zmanjšanje DB obremenitve); prenosljiv datum format na kartici; popravek es_stevilka tipa; dashboard agregatne poizvedbe |
| v1.26 | Nadgradnja varnostnih odvisnosti: jinja2 3.1.6 (sandbox bypass), starlette 0.52.1 (Range DoS + multipart DoS), python-multipart 0.0.22 (path traversal), FastAPI 0.135.1 |
| v1.27 | CSRF v obrazcu za brisanje uporabnika (C1); odjava POST + CSRF (H1); rate limiting na profil operacijah (H2); per-username lockout (H3) |
| v1.28 | python-multipart 0.0.27 (multipart DoS), pytest 9.0.3 (dev) |
| v1.29 | Shranjeni XSS v JS atributih (`data-confirm` + globalni handler); CSP z nonce + SRI; `UserValidationMiddleware`; produkcijske zahteve ob zagonu (SECRET_KEY, ADMIN_GESLO); TOTP replay zaščita; bcrypt tudi za neobstoječega uporabnika; SMTP timeout + threadpool; admin ne more spremeniti lastne vloge; `PRAGMA foreign_keys=ON` + Alembic 010; brisanje skupin samo admin; razširjen audit log; ZRS Content-Disposition sanitizacija; AKOS URL-kodiranje; SQLite backup API; fastapi 0.141.1 / starlette 1.6.0 / python-multipart 0.0.32 / uvicorn 0.53.0 |

---

## Priporočen vrstni red odprave

1. **Pred vsakim zagonom:** Nastaviti `SECRET_KEY` in `ADMIN_GESLO` v `.env` (K1, K2) – v produkciji je to od v1.29 obvezno, sicer se aplikacija ne zažene
2. **Lokalna ali VPN uporaba:** Ni potrebnih dodatnih ukrepov – promet ne zapusti zaupljivega omrežja
3. **Pred javnim dostopom:** HTTPS + HSTS na reverse proxy-u (Synology ali Nginx) – brez sprememb kode (V1)
4. **Priporočeno za vse uporabniške račune:** Aktivirati 2FA prek Moj profil → Aktiviraj 2FA (posebej za admin)
5. **Operativno:** Redni `pip-audit`; periodično čiščenje audit loga (N2, N5)

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

# Zaupljive naprave (aktivne – ne potekle)
sqlite3 data/clanstvo.db "
SELECT u.uporabnisko_ime, n.created_at, n.expires_at, substr(n.user_agent, 1, 60)
FROM zaupljive_naprave n JOIN uporabniki u ON u.id = n.uporabnik_id
WHERE n.expires_at > datetime('now')
ORDER BY n.created_at DESC;"

# Izbriši vse zaupljive naprave (prisili vse 2FA uporabnike k OTP)
sqlite3 data/clanstvo.db "DELETE FROM zaupljive_naprave;"
```
