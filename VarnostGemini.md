# Varnostna analiza aplikacije – Upravljanje Članstva

*Pripravil: Gemini CLI | Datum: 2026-02-24*

---

## 1. Povzetek varnostnega stanja

Aplikacija "Upravljanje Članstva" izkazuje visoko stopnjo zrelosti na področju varnosti za namensko programsko opremo. Implementirani so standardni zaščitni mehanizmi (bcrypt, CSRF zaščita, audit log, 2FA), ki presegajo osnovne zahteve za lokalna orodja. 

Največje tveganje predstavljata **privzeta konfiguracija** in **odsotnost prisilne uporabe HTTPS**, kar je v dokumentaciji sicer izpostavljeno, a ostaja odgovornost skrbnika.

---

## 2. Ključne prednosti (Security Strengths)

- **Večnivojska avtentikacija:** Vključitev opcijske TOTP 2FA (RFC 6238) v različici v1.12 znatno povečuje varnost skrbniških računov.
- **Robustna politika gesel:** Zahteva po 14+ znakih z mešanimi tipi znakov je nadpovprečna in učinkovito preprečuje uporabo šibkih gesel.
- **Zaščita pred pogostimi napadi:**
    - **SQL Injection:** Uporaba SQLAlchemy ORM in parametriziranih poizvedb.
    - **XSS:** Jinja2 samodejno izhaja (auto-escape) vsebino; ročni `| safe` se uporablja le za varno generiran QR kodo.
    - **CSRF:** Implementirana lastna zaščita s žetoni na vseh POST zahtevah.
    - **Brute-force:** Rate limiting (10 poskusov / 15 min) na nivoju IP naslova.
- **Audit Log:** Beleženje vseh kritičnih akcij (prijave, CRUD operacije, izvozi) omogoča sledljivost in detekcijo zlorab.
- **Varno upravljanje sej:** Uporaba `SameSite=Strict` in podpisovanje piškotkov preprečujeta krajo sej in CSRF napade.

---

## 3. Identificirana tveganja in ranljivosti

### 3.1 Kritična tveganja (High Priority)
- **Okoljske spremenljivke:** Če skrbnik ne spremeni `SECRET_KEY` in `ADMIN_GESLO` v `.env`, je aplikacija trivialno ranljiva. `SECRET_KEY` omogoča ponarejanje sejnih piškotkov.
- **Prenos v čistem tekstu:** Aplikacija sama ne izvaja HTTPS. Brez pravilno nastavljenega reverse proxy-ja (Nginx) so vsi podatki, vključno z gesli, izpostavljeni prestrezanju v lokalnem omrežju.

### 3.2 Srednja tveganja (Medium Priority)
- **Hranjenje rate limiting podatkov:** Trenutni števec neuspelih prijav se hrani v delovnem pomnilniku (RAM). Ob ponovnem zagonu vsebnika se števec resetira, kar lahko napadalec izkoristi za dolgotrajne brute-force napade.
- **Odsotnost omejitve seje:** Seja poteče šele po 1 uri, ne glede na aktivnost uporabnika. Na deljenih računalnikih to predstavlja tveganje nepooblaščenega dostopa.
- **Nenadzorovana rast audit loga:** Tabela `audit_log` raste z vsakim ogledom člana. Brez avtomatskega čiščenja lahko dolgoročno povzroči zapolnitev diska.

---

## 4. Priporočila za izboljšavo

1. **Prisilna nastavitev ključev:** Implementirati preverjanje ob zagonu (`main.py`), ki prepreči zagon aplikacije, če je `SECRET_KEY` nastavljen na privzeto vrednost.
2. **Implementacija "Inactivity Timeout":** Dodati middleware, ki po npr. 20 minutah neaktivnosti samodejno odjavi uporabnika.
3. **Trajen Rate Limiting:** Shranjevanje neuspelih prijav v SQLite tabelo namesto v diktat v pomnilniku.
4. **HSTS Header:** Ko je HTTPS aktiviran, dodati `Strict-Transport-Security` glavo za prisilno uporabo varne povezave v brskalniku.
5. **Validacija vlog:** V routerjih za upravljanje uporabnikov dodati striktno validacijo, da vloga ne more biti poljuben niz (čeprav trenutno to ne omogoča eskalacije privilegijev).

---

## 5. Podrobne tehnične ugotovitve (Code-level Review)

### 5.1 Avtentikacija in seje
- **Session Fixation:** Aplikacija se pravilno zaščiti s klicem `request.session.clear()` ob prijavi.
- **Timing Attacks:** V `app/main.py` se geslo vedno preveri (`preveri_geslo`), tudi če uporabnik ne obstaja, kar preprečuje ugotavljanje obstoja uporabniških imen na podlagi odzivnega časa.
- **CSRF Zaščita:** Implementacija v `app/csrf.py` uporablja `secrets.compare_digest`, kar je kriptografsko varno.

### 5.2 Rate Limiting in DoS tveganja
- **Memory Exhaustion (DoS):** Trenutna implementacija rate limitinga v `app/main.py` uporablja `_login_attempts: dict`. Ker ta slovar nima omejitve števila vnosov (IP naslovov), lahko napadalec s porazdeljenim napadom (DDoS) zapolni celoten RAM strežnika.
- **Reset ob ponovnem zagonu:** Ker se podatki o poskusih ne shranjujejo trajno, ponovni zagon aplikacije izniči vse blokade.

### 5.3 Upravljanje s podatki
- **SQL Injection:** Dosledna uporaba SQLAlchemy ORM v vseh routerjih učinkovito preprečuje SQL injection napade.
- **Prikaz začasnih gesel:** Pri ponastavitvi gesla se novo geslo shrani v `request.session["zacasno_geslo"]`. Čeprav je seja na strežniku, se podatki prenašajo v podpisanem piškotku. V kodi `app/routers/uporabniki.py` se uporablja `.pop()`, kar je pravilno, vendar geslo ostane v piškotku do konca trenutnega zahtevka.

### 5.4 Infrastruktura (Docker)
- **Omejitev mrežnega vmesnika:** `docker-compose.yml` pravilno omejuje izpostavljenost vrat na `127.0.0.1`, kar zmanjšuje površino napada.
- **Healthcheck:** Vključen healthcheck v Dockerju uporablja `python` kodo za klic `urllib`, kar je varno, vendar bi bilo za produkcijo primernejše orodje `curl`.

---

## 6. GDPR skladnost

Aplikacija vsebuje vse potrebne gradnike za doseganje GDPR skladnosti (beleženje dostopa, možnost izvoza podatkov, brisanje), vendar mora končni upravljavec (klub) sam urediti pravno podlago (soglasja) in zagotoviti varno gostovanje (šifriranje diska, HTTPS).

---

## 7. Sklepna ocena

Koda je napisana z varnostjo v mislih in sledi modernim standardom za Python/FastAPI aplikacije. Glavne pomanjkljivosti so operativne narave (konfiguracija .env, HTTPS) in specifično tveganje DoS napada na rate limiting mehanizem.

---
*Opomba: Ta analiza je bila opravljena na podlagi podrobnega pregleda izvorne kode in priložene dokumentacije v1.12.*
