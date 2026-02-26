# Analiza izboljšav – Radio klub Člani – Upravljanje Članstva

## Implementirane funkcionalnosti

| Funkcija | Status | Različica | Opomba |
|---|---|---|---|
| Prijava z vlogami (admin/urednik/bralec) | ✅ | v1.0 | Session cookie, bcrypt gesla |
| CRUD za člane | ✅ | v1.0 | Dodaj, uredi, izbriši (admin) |
| Iskanje in filtri | ✅ | v1.0 | DataTables + server-side filtri |
| Evidenca plačil članarine | ✅ | v1.0 | Po letih, datum + znesek |
| Uvoz iz Excel | ✅ | v1.0 | Samodejno mapiranje stolpcev |
| Izvoz za ZRS | ✅ | v1.0 | Format prijava_clanov_YYYY.xlsx |
| Excel backup | ✅ | v1.0 | Vsi člani + plačila |
| SQLite backup | ✅ | v1.0 | Surova DB datoteka |
| Upravljanje uporabnikov | ✅ | v1.0 | Admin funkcija |
| Nastavitve kluba | ✅ | v1.0 | ZRS podatki |
| Nastavljivi tipi članstva | ✅ | v1.1 | V nastavitvah, ena vrednost na vrstico |
| Nastavljivi operaterski razredi | ✅ | v1.1 | V nastavitvah, ena vrednost na vrstico |
| Znesek plačila v evidenci | ✅ | v1.1 | Polje za vsak vnos |
| Docker Deploy | ✅ | v1.0 | docker compose up -d |
| Ponastavitev gesla (admin) | ✅ | v1.2 | Generira začasno geslo, enkratni prikaz prek session flash |
| Seštevki plačil po letu | ✅ | v1.2 | Na izvoz strani: leto → count → skupaj € |
| Filter veljavnosti RD licence | ✅ | v1.2 | potekla/kmalu/veljavna/brez + barvna oznaka |
| Varnostni HTTP headers | ✅ | v1.2 | SecurityHeadersMiddleware |
| Rate limiting prijave | ✅ | v1.2 | 10 poskusov / 15 min per IP |
| CSRF zaščita | ✅ | v1.3 | Per-session token, Depends(csrf_protect) na vseh POST |
| Validacija gesel | ✅ | v1.3 | Min 14 znakov, upper+lower+digit+special |
| Profilna stran + sprememba gesla | ✅ | v1.3 | /profil – ime + geslo za vse vloge |
| Evidenca aktivnosti | ✅ | v1.4 | Na strani člana, neomejeno vnosov/leto, v backup |
| Skupinsko upravljanje članov | ✅ | v1.5 | Many-to-many, CRUD skupin, prikaz na strani člana |
| Filter let za plačila in aktivnosti | ✅ | v1.6 | Vse / Zadnji 2 leti / Zadnjih 10 let, JS client-side |
| Delovne ure v evidenci aktivnosti | ✅ | v1.6 | Numerično polje, v backup Excel |
| Posodobljeni tipi članstva | ✅ | v1.7 | Osebni, Družinski, Simpatizerji, Mladi, Invalid + samodejna migracija |
| Normalizacija vnosnih podatkov | ✅ | v1.7 | Title case priimek/ime, uppercase KZ, email validacija, allowlist tip |
| Audit log | ✅ | v1.7 | Tabela audit_log, admin pregled /audit, izvoz Excel |
| Predogled uvoza Excel | ✅ | v1.8 | 2-koračni tok: predogled (POST /uvozi) → potrditev (POST /uvozi-potrdi); temp file v data/tmp/ |
| Mobilna optimizacija | ✅ | v1.8 | DataTables Responsive, table-responsive wrappers, mobilni CSS breakpoint |
| Type hints za route funkcije | ✅ | v1.8 | Vseh 38 async def dobi `-> Response / RedirectResponse / dict`; rm unused Optional |
| Unit testi | ✅ | v1.8 | pytest: 34 testov v 6 datotekah (auth, csrf, normalizacija, config, audit_log, routes) |
| Konfigurabilno mapiranje stolpcev uvoza | ✅ | v1.9 | UVOZ_STOLPCI_PRIVZETO v izvoz.py; urejanje v /uvozi; vejica = alternativna imena stolpcev |
| Dokumentacija | ✅ | v1.9 | Uporabniski-prirocnik.md, Tehnicna-dokumentacija.md; posodobljen README.md |
| Konfigurabilni ZRS Excel izvoz | ✅ | v1.10 | Uppercase transformacija; mapiranje tipov (Mladi→Mladi-18 let, Simpatizerji izključeni); mapiranje operaterskih razredov; nastavljivi stolpci (naziv, vrstni red, vključi/izključi); nastavitve inline na /izvoz |
| Generičen klub – brez trdih referenc | ✅ | v1.10 | KlubContextMiddleware; dinamičen navbar/title prek request.state; nastavitve uvoza premaknjene na /uvozi; docker-compose generičen |
| Ločen uvoz plačil | ✅ | v1.11 | Uvoz članov ne uvozi več plačil; ločen obrazec za uvoz plačil s stolpci Priimek, Ime, Datum plačila, Znesek; leto se določi iz datuma; identifikacija po priimku+imenu; upsert obstoječih; 2-koračni predogled; nastavljivi stolpci |
| Opcijska 2FA avtentikacija (TOTP) | ✅ | v1.12 | pyotp + segno; Uporabnik.totp_skrivnost/totp_aktiven; /login/2fa za OTP korak; /profil/2fa-nastavi (QR SVG); /profil/2fa-potrdi; /profil/2fa-onemogoči; rate limiting reuse; audit log |
| Zaupljiva naprava – 2FA "zapomni (30 dni)" | ✅ | v1.12 | Checkbox na 2FA strani; SHA-256 hashed token v zaupljive_naprave; 30-dnevni httponly cookie; pregled in odjava naprav na profilu; audit log login_2fa_zaupljiva |
| Alembic migracije | ✅ | v1.12 | Zamenjava ročnih ALTER TABLE; alembic/versions/001 (vse tabele) + 002 (zaupljive_naprave); auto-stamp obstoječih baz kot 001 |
| Logging v datoteko | ✅ | v1.12 | RotatingFileHandler → data/app.log; 5 MB × 5 datotek; konfiguriran v _nastavi_logging() ob zagonu |
| ProxyHeadersMiddleware | ✅ | v1.12 | Uvicorn ProxyHeadersMiddleware (trusted_hosts="*"); bere X-Forwarded-For/X-Real-IP od reverse proxy-a; pravilni IP v audit logu |
| Uvoz ES-številke in opomb iz Excel | ✅ | v1.13 | Dve novi polji (es_stevilka, opombe) dodani v UVOZ_STOLPCI_PRIVZETO; es_stevilka se parsira kot int |
| Privzeti operaterski razredi razširjeni | ✅ | v1.13 | OPERATERSKI_RAZREDI_PRIVZETO: A, N, A - CW, N - CW |
| Persistentni rate limiting | ✅ | v1.13 | Nova tabela login_poskusi (ip, cas); auto-cleanup starih vnosov; Alembic migracija 003; zamenjal in-memory defaultdict |
| Omejitev velikosti POST zahtevkov (1 MB) | ✅ | v1.13 | ContentSizeLimitMiddleware; izvozne poti (/izvoz/*) izvzete – imajo lastno 10 MB omejitev |
| Iztok seje ob neaktivnosti (30 min) | ✅ | v1.13 | InactivityTimeoutMiddleware; _last_active timestamp v seji; redirect /login?timeout=1 z opozorilom |
| Validacija vloge pri urejanju uporabnikov | ✅ | v1.13 | Preprečuje neustrezne vloge; fallback na "bralec" v obeh POST handlerjih |
| Začasno geslo ustreza politiki | ✅ | v1.13 | 16 znakov; garantirano upper+lower+digit+special (!@#$%*-_+?); Fisher-Yates mešanje |
| Značka različice aplikacije v footerju | ✅ | v1.13 | vX.XX + datum izdaje + besedilo LICENSE; Bootstrap modal; vrednosti prek KlubContextMiddleware |

---

## Predlagane izboljšave (backlog)

### Visoka prioriteta

#### ~~1. Ponastavitev gesla~~ ✅ Implementirano v v1.2

#### ~~2. Evidenca plačil – skupni seštevki~~ ✅ Implementirano v v1.2

#### ~~3. Filtriranje po veljavnosti RD licence~~ ✅ Implementirano v v1.2

#### ~~4. Predogled uvoza~~ ✅ Implementirano v v1.8
*(2-koračni tok: parsiranje → predogled tabele → potrditev uvoza)*

---

### Srednja prioriteta

#### 5. Obvestila po e-pošti
- **Problem:** Ni samodejnih opozoril za neplačane članarine ali potekle licence.
- **Predlog:** Cron job (v Docker-ju) ki pošlje e-mail seznam admin-u enkrat letno (npr. 1. februar).
- **Tehnologija:** Python smtplib, možna integracija z SMTP relayjem ali SendGrid.
- **Obseg:** ~4 ure

#### ~~6. Dnevnik sprememb (audit log)~~ ✅ Implementirano v v1.7

#### 7. Uvoz plačil za več let hkrati
- **Problem:** Uvoz iz Excel podpira samo eno leto naenkrat.
- **Predlog:** Pri uvozu samodejno prepoznaj vse stolpce z letnicami in uvozi vse hkrati.
- **Obseg:** ~2 uri (dopolnitev obstoječe uvoz logike)

#### 8. QR koda za plačilo
- **Problem:** Ročno vnašanje podatkov za UPN plačilni nalog.
- **Predlog:** Generiranje UPN QR kode za vsakega neplačanega člana (knjižnica `qrcode`).
- **Obseg:** ~3 ure

---

### Nizka prioriteta / Nice-to-have

#### 9. Večjezična podpora
- **Problem:** UI je samo v slovenščini.
- **Predlog:** Dodati angleške prevode za morebitne tuje člane.
- **Obseg:** ~4 ure

#### ~~10. Mobilna optimizacija~~ ✅ Implementirano v v1.8
*(DataTables Responsive, table-responsive wrappers, CSS breakpoint za 576px)*

#### ~~11. Profilna stran~~ ✅ Implementirano v v1.3
*(Profilna stran za app. uporabnike – ime in geslo. Profilna stran za člane kluba je še odprt backlog.)*

#### 12. Statistični dashboard
- **Problem:** Ni grafičnega prikaza stanja članstva.
- **Predlog:** Domača stran z grafi: trend članstva po letih, plačila po mesecih, razporeditev tipov.
- **Tehnologija:** Chart.js (CDN, brez build koraka).
- **Obseg:** ~4 ure

---

## Znane omejitve trenutne različice

| Omejitev | Opis | Možna rešitev |
|---|---|---|
| SQLite | Ni primerno za 100+ sočasnih uporabnikov | Zamenjava z PostgreSQL |
| Brez HTTPS | HTTP samo – za lokalno omrežje sprejemljivo | Nginx / Synology reverse proxy + Let's Encrypt |
| Brez avtomatskega backupa | Backup je ročen | Cron job v Docker-ju |

---

## Tehnični dolg

- [x] Dodati tip hints za vse route funkcije – implementirano v v1.8
- [x] Dodati validacijo vnosnih podatkov (email, allowlist, normalizacija) – implementirano v v1.7
- [x] Pisati unit teste za kritične funkcije (auth, csrf, normalizacija, config, audit, routes) – implementirano v v1.8
- [x] Alembic migracije namesto ročnih ALTER TABLE – implementirano v v1.12
- [x] Logging v datoteko namesto samo na stdout – implementirano v v1.12

---

*Zadnja posodobitev: 2026-02-26 (v1.13)*
