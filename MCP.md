# MCP – Analiza implementacije za Upravljanje Članstva

*Datum analize: 2026-03-05 | Posodobljeno: 2026-03-31 (ažurirano za v1.26) | Aplikacija: v1.26*

---

## Kazalo

1. [Kaj je MCP](#1-kaj-je-mcp)
2. [Relevantnost za to aplikacijo](#2-relevantnost-za-to-aplikacijo)
3. [Potencialni primeri uporabe](#3-potencialni-primeri-uporabe)
4. [Predlagane MCP primitive](#4-predlagane-mcp-primitive)
5. [Arhitekturne možnosti implementacije](#5-arhitekturne-možnosti-implementacije)
6. [Priporočena arhitektura](#6-priporočena-arhitektura)
7. [Varnostna analiza](#7-varnostna-analiza)
8. [Tehnične ovire in tveganja](#8-tehnične-ovire-in-tveganja)
9. [Predlagane faze implementacije](#9-predlagane-faze-implementacije)
10. [Ocena obsega dela](#10-ocena-obsega-dela)
11. [Sklep](#11-sklep)

---

## 1. Kaj je MCP

**Model Context Protocol (MCP)** je odprt standard, ki ga je razvil Anthropic. Omogoča AI aplikacijam (Claude Desktop, Claude Code, ali lastni AI asistenti) standardiziran dostop do zunanjih sistemov – podatkovnih baz, datotek, API-jev in orodij.

MCP strežnik aplikacije izpostavi tri vrste primitiv:

| Primitiva | Opis | Primer za klub |
|-----------|------|----------------|
| **Resources** | Podatki, ki jih AI bere | Seznam članov, plačila, statistika |
| **Tools** | Akcije, ki jih AI izvede | Zabeleži plačilo, pošlji obvestilo |
| **Prompts** | Predpripravljene poizvedbe | "Poročilo za skupščino" |

Transport je bodisi **stdio** (MCP strežnik teče kot lokalni subprocess – za Claude Desktop) ali **HTTP/SSE** (za oddaljene integracije).

---

## 2. Relevantnost za to aplikacijo

Aplikacija za upravljanje članstva radiokluba hrani strukturirane podatke (člani, plačila, aktivnosti), ki so pogosto predmet ad-hoc poizvedb s strani poslovodstva kluba. Trenutno je vsaka poizvedba vezana na ročno brskanje po spletnem vmesniku.

**Vrednost MCP integracije:** Tajnik ali predsednik kluba bi z naravnim jezikom prek Claude Desktop ali podobne AI aplikacije lahko:
- dobil odgovor na vprašanje brez prijave v spletni vmesnik,
- izvedel zapletene poizvedbe ki jih UI ne podpira direktno,
- generiral poročila v sekundah,
- sprožil akcije (pošlji obvestilo, zabeleži plačilo) z naravnim ukazom.

---

## 3. Potencialni primeri uporabe

### 3.1 Poizvedbe (samo branje)

```
"Kdo ni plačal članarine za leto 2026?"
→ MCP tool: neplacniki(leto=2026)
→ Odgovor: tabela z imeni, e-pošto, tipom členstva

"Koliko aktivnih članov ima klub?"
→ MCP resource: clanstvo://dashboard
→ Odgovor: statistike

"Pokaži mi vse člane, katerim potečejo radijska dovoljenja v naslednjih 30 dneh."
→ MCP tool: filtriraj_clane(rd_potece_v_dneh=30)
→ Odgovor: seznam s klicnimi znaki in datumi

"Ana Novak ima novi naslov: Ulica 5, 6000 Koper. Posodobi jo."
→ MCP tool: posodobi_clan(id=..., naslov_ulica="Ulica 5", naslov_posta="6000 Koper")
→ Potrditev + audit log
```

### 3.2 Generiranje poročil

```
"Pripravi poročilo za letno skupščino: število članov, plačila za 2025, aktivnosti."
→ Več resource/tool klicev → strukturirano Markdown poročilo

"Izvozi seznam vseh neplačnikov z e-poštnimi naslovi v CSV."
→ MCP tool → CSV vsebina v odgovoru
```

### 3.3 Vloge in članske kartice *(novo v1.15–v1.23)*

```
"Kdo je trenutni predsednik kluba?"
→ MCP tool: vloge_clanov(naziv="Predsednik", aktivne=true)
→ Odgovor: ime, priimek, datum_od

"Generiraj člansko kartico za S59ABC za leto 2026."
→ MCP tool: generiraj_kartico(clan_id=17, leto=2026)
→ Odgovor: PDF bytes (85.6×54 mm kartica)

"Pošlji člansko kartico Janezu Novaku za 2026."
→ MCP tool: posli_kartico(clan_id=42, leto=2026)
→ Potrditev: "Kartica poslana na janez@example.com"
```

### 3.4 Sprožanje akcij

```
"Pošlji UPN QR poziv k plačilu vsem neplačnikom za 2026."
→ MCP tool: bulk_posli_obvestilo(bulk_filter="neplacniki", leto=2026, predloga_id=1)
→ Potrdi: "Poslano 12 e-poštnih sporočil, preskočeni 3 (brez e-pošte)"

"Janez Novak je plačal članarino za 2026, 25 EUR."
→ MCP tool: dodaj_clanarina(clan_id=42, leto=2026, znesek="25.00")
→ Potrditev
```

---

## 4. Predlagane MCP primitive

### 4.1 Resources (branje)

| URI | Opis |
|-----|------|
| `clanstvo://clani` | Seznam vseh aktivnih članov (ime, priimek, klicni_znak, tip) |
| `clanstvo://clani/{id}` | Celotna kartica posameznega člana |
| `clanstvo://clani/{id}/vloge` | Vloge člana z zgodovino (datum_od, datum_do) *(v1.15+)* |
| `clanstvo://clanarine/{leto}` | Plačila za izbrano leto |
| `clanstvo://aktivnosti/{leto}` | Aktivnosti za izbrano leto |
| `clanstvo://dashboard` | Statistični povzetek (aktivni, plačali, neplačali, delovne ure) |
| `clanstvo://email-predloge` | Razpoložljive e-poštne predloge (6 privzetih, vključno QR in kartica) |
| `clanstvo://nastavitve` | Javne nastavitve kluba (ime, oznaka, tipi, UPN podatki, kartica_polja) |

### 4.2 Tools (dejanja)

| Tool | Parametri | Opis | Faza |
|------|-----------|------|------|
| `isci_clane` | `q: str`, `aktiven: bool?` | Iskanje po imenu, priimku, klicnem znaku | 1 (branje) |
| `filtriraj_neplacnike` | `leto: int` | Vrne seznam neplačnikov z e-pošto | 1 (branje) |
| `filtriraj_placnike` | `leto: int` | Vrne seznam plačnikov za leto *(v1.23+)* | 1 (branje) |
| `filtriraj_rd_potece` | `v_dneh: int` | Člani s potečeno ali skoraj potečeno RD (privzeto 180 dni) | 1 (branje) |
| `vloge_clanov` | `naziv: str?`, `aktivne: bool?` | Vloge članov, opcijsko filtrirane po nazivu *(v1.15+)* | 1 (branje) |
| `statistika_leto` | `leto: int` | Plačila in aktivnosti za leto (agregatne poizvedbe) | 1 (branje) |
| `dodaj_clanarina` | `clan_id, leto, znesek, datum?` | Zabeleži plačilo (upsert) | 2 (pisanje) |
| `dodaj_aktivnost` | `clan_id, leto, opis, ure?` | Zabeleži aktivnost | 2 (pisanje) |
| `posodobi_clan` | `id, **polja` | Posodobi podatke člana | 2 (pisanje) |
| `posli_obvestilo` | `predloga_id, leto, clan_id?/bulk_filter?` | Pošlji e-pošto (bulk filtri: neplacniki, placniki, rd_potekla, rd_kmalu, vsi_aktivni, vsi) | 2 (pisanje) |
| `generiraj_kartico` | `clan_id: int, leto: int` | Generira PDF člansko kartico (85.6×54 mm) *(v1.23+)* | 2 (pisanje) |
| `posli_kartico` | `clan_id: int, leto: int` | Pošlje PDF kartico na email člana *(v1.23+)* | 2 (pisanje) |

> **Opomba:** Od v1.24 obstaja JSON endpoint `GET /clani/iskanje?q=...` (autocomplete),
> ki je de facto prvi API-like endpoint v aplikaciji. Vrača `[{id, priimek, ime, klicni_znak, elektronska_posta, aktiven}]`.
> Ta vzorec je neposredno uporaben za MCP tool `isci_clane`.

### 4.3 Prompts

| Prompt | Opis |
|--------|------|
| `porocilo_skupscina` | Parametriziran poziv za letno skupščinsko poročilo |
| `pregled_neplacniki` | Pregled neplačnikov z možnostjo takojšnjega pošiljanja |
| `pregled_rd` | Pregled veljavnosti RD za vse člane |

---

## 5. Arhitekturne možnosti implementacije

### Možnost A: Neposreden dostop do SQLite

MCP strežnik odpre lastno SQLAlchemy sejo direktno na `data/clanstvo.db`.

```
Claude Desktop
  → subprocess: python mcp_server.py (stdio)
  → SQLAlchemy → data/clanstvo.db (isti file kot aplikacija)
```

**Prednosti:**
- Najenostavnejša implementacija
- Brez omrežnega overhead
- Nativna hitrost poizvedb

**Slabosti:**
- **Obide obstoječi audit log** – spremembe prek MCP ne bodo zabeležene
- **Obide CSRF zaščito** – ni seanse, ki bi jo zaščitili
- Pri pisalnih operacijah: potencialni `database is locked` pri sočasnem pisanju (SQLite WAL mode reši branje, ne nujno pisanja)
- Poslovna logika mora biti replicirana (normalizacija, validacija)

### Možnost B: HTTP klici na obstoječe FastAPI endpointe

MCP strežnik kliče obstoječe `/clani`, `/clanarine`, ... endpointe z upravljanjem seje.

```
Claude Desktop
  → subprocess: python mcp_server.py (stdio)
  → HTTP requests → FastAPI (localhost:8000)
  → obstoječi routerji → SQLite
```

**Prednosti:**
- Vsa obstoječa logika, validacija, normalizacija ostane nespremenjena
- Audit log deluje
- CSRF zaščita deluje (MCP strežnik upravlja sejo in CSRF token)

**Slabosti:**
- Zahteva tekoč FastAPI strežnik (odvisnost)
- CSRF token management je zapleten (MCP strežnik mora pridobiti token pred vsakim POST-om)
- Session-based auth je nerodna za programski dostop (login → session cookie)

### Možnost C: Novi `/api/v1/` endpointi z API ključem

Obstoječi aplikaciji se dodajo namenski API endpointi z Bearer token avtentikacijo (brez CSRF, namesto nje API ključ).

```
Claude Desktop
  → subprocess: python mcp_server.py (stdio)
  → HTTP z Bearer token → FastAPI /api/v1/... → SQLite
```

**Prednosti:**
- Arhitekturno najčistejše
- Audit log piše `"api_kljuc_xxx"` kot uporabnika
- Odpira pot za prihodnje integracije (ne samo MCP)
- CSRF ni potreben (Bearer token je zadosten za programski dostop)

**Slabosti:**
- Največ dela: novi endpointi + API ključ auth middleware
- Morebitna podvajanja logike med web in API endpointi (ali refaktoriranje na skupne service funkcije)

### Možnost D: Samo branje, neposreden SQLite + stdio

Konzervativni pristop: MCP strežnik izpostavi samo bralne operacije direktno iz DB, brez kakršnih koli pisanj.

```
Claude Desktop
  → subprocess: python mcp_server.py (stdio)
  → SQLAlchemy read-only → data/clanstvo.db
```

**Prednosti:**
- Nič tvegano – samo branje, brez stranskih učinkov
- Enostavno implementirati (1–2 dni dela)
- SQLite podpira vzporedne bralce brez blokad

**Slabosti:**
- AI ne more sprožati akcij (pošiljanja, vnosov)
- Omejena vrednost za dejansko delo

---

## 6. Priporočena arhitektura

**Priporočam dvofazni pristop:**

### Faza 1: Bralni MCP strežnik (Možnost D)

Implementira se ločen Python MCP strežnik, ki:
- teče kot **stdio subprocess** (za Claude Desktop)
- odpre **read-only** SQLAlchemy sejo na isti `data/clanstvo.db`
- izpostavi resources in bralne tools (brez pisanja)

To je nizko tvegano, hitro implementirati in takoj koristno za poizvedbe in poročila.

### Faza 2: Razširitev z API endpointi (Možnost C)

Za pisalne operacije (dodaj plačilo, pošlji obvestilo):
- V obstoječo FastAPI aplikacijo se dodajo `/api/v1/` endpointi
- Avtentikacija prek `X-API-Key` headerja (API ključ shranjen v `nastavitve` tabeli)
- MCP strežnik te endpointe kliče s ključem
- Audit log zapiše `"mcp_api"` kot uporabnika

### Topologija za produkcijsko okolje

Za klub z Synology NAS deploymentom:

```
Claude Desktop (na računalniku tajnika/predsednika)
    │
    │ stdio (lokalni subprocess)
    ▼
mcp_server.py (teče lokalno)
    │
    ├── read-only SQLAlchemy → SMB/SFTP → data/clanstvo.db (NAS)
    │                          ali
    └── HTTP API klici → https://clani.s59dgo.org/api/v1/... (NAS)
```

Za enostavnost lokalne namestitve je **stdio + neposreden DB dostop** (vsaj za branje) najpraktičnejši, ker ne zahteva, da je aplikacija dostopna z interneta.

---

## 7. Varnostna analiza

### 7.1 Grožnje specifične za MCP

| Grožnja | Opis | Ukrep |
|---------|------|-------|
| **Prompt injection** | Zlonamerna vsebina v DB poljih (opombe člana) zavede AI k nepooblaščenim akcijam | Pisalni tools zahtevajo potrditveni korak; vnos se ne izvede brez eksplicitne potrditve |
| **Prekomerne pravice** | MCP strežnik z admin pravicami dopušča preširoke operacije | MCP tools implementirajo lastno dovoljenje (npr. samo branje, brez brisanja) |
| **API ključ leak** | API ključ v lokalnih datotekah ali logih | Ključ shranjen v `nastavitve` tabeli (šifriran z SECRET_KEY) ali v `.env` |
| **Sočasni dostop SQLite** | MCP in aplikacija pišeta hkrati | Faza 1 je samo branje; faza 2 pisanja gredo prek aplikacije (en pisec) |
| **Tool poisoning** | Zlonamerni MCP strežnik se pretvarja za legitimnega | Claude Desktop prikazuje katere MCP strežnike ima naložene – pregled ob namestitvi |

### 7.2 Pozitivni varnostni vidiki

- **stdio transport** je lokalni subprocess – ni mrežne izpostavljenosti
- MCP strežnik se izvaja z omejenimi pravicami lokalnega uporabnika
- **Audit trail**: vse AI akcije so zabeležene v `audit_log` (pri Fazi 2)
- MCP ne nadomešča obstoječe auth – UI vmesnik ostane nespremenjen

### 7.3 Priporočila

- MCP strežnik implementira **whitelist dovoljenih operacij** (tools ki obstajajo)
- Pisalni tools imajo vgrajen **opozorni korak** (tool vrne "Ali ste prepričani?" opis pred izvedbo)
- API ključ za MCP je ločen od admin gesel in ga je mogoče preklicati
- Ves dostop do DB iz MCP je **read-committed** izolacija (SQLAlchemy privzeto)

---

## 8. Tehnične ovire in tveganja

### 8.1 SQLite sočasni dostop (Faza 1)

SQLite pri privzetem `DELETE` journal načinu podpira vzporedne bralce. Pri `WAL` načinu (ki ga aplikacija ne nastavi eksplicitno) je to še bolj robustno. Tveganje za bralne operacije je **zanemarljivo**.

### 8.2 Replikacija poslovne logike

MCP strežnik bi moral replicirati nekatere poizvedbe (npr. neplačniki = `NOT IN subquery clanarine`). To ustvari dve mesti za vzdrževanje. **Rešitev:** skupna `app/queries.py` datoteka s shared query funkcijami, ki jo uporabljata tako FastAPI router kot MCP strežnik.

Od v1.25 dashboard uporablja **agregatne SQL poizvedbe** (2 poizvedbi namesto 20, z `GROUP BY` in `func.sum/func.count`). Te poizvedbe so idealne za izločitev v `app/queries.py` in neposredno uporabo v MCP tool `statistika_leto`.

### 8.3 Odvisnost od running aplikacije (Faza 2)

HTTP klici na `/api/v1/` zahtevajo, da FastAPI strežnik teče. Za lokalni MCP (stdio) je to OK – aplikacija vseeno teče. Za **offline scenarije** (tajnik kliče Claude, aplikacija je ugasnjena) Faza 2 ne deluje; Faza 1 (neposreden DB) deluje.

### 8.4 Sinhronizacija sheme

Ob vsaki spremembi podatkovnega modela (nova tabela, novo polje) je treba posodobiti tudi MCP strežnik. Od v1.19 so bile dodane 3 nove Alembic migracije (006 indeksi, 007 vkljuci_qr, 008 prilozi_kartico) — skupaj je zdaj **8 migracij**. Modeli vključujejo: `Clan`, `Clanarina`, `Aktivnost`, `Skupina`, `Uporabnik`, `Nastavitev`, `AuditLog`, `ZaupljivaNaprava`, `LoginPoizkus`, `ClanVloga`, `EmailPredloga`.

**Rešitev:** MCP strežnik uvozi modele iz `app/models.py` – isti SQLAlchemy razredi. Ker MCP Faza 1 ne poganja migracij (read-only), mora aplikacija teči vsaj enkrat pred MCP uporabo, da se baza posodobi.

### 8.5 Namestitvena zapletenost za končnega uporabnika

Claude Desktop zahteva konfiguracijo `claude_desktop_config.json` z absolutno potjo do MCP strežnika. Za netehničnega tajnika kluba je to ovira. **Rešitev:** install skripta ali README z natančnimi navodili.

---

## 9. Predlagane faze implementacije

### Faza 1: Bralni MCP strežnik

**Cilj:** Claude Desktop lahko odgovarja na vprašanja o članih, plačilih, vlogah in statistiki.

**Datoteke:**
- `mcp_server.py` – MCP strežnik (stdio, Python `mcp` SDK)
- `app/queries.py` – shared poizvedbe (izločene iz routerjev, vključno dashboard agregatne)
- `mcp_requirements.txt` – odvisnosti za MCP (`mcp`, `sqlalchemy`)
- `docs/mcp_namestitev.md` – navodila za Claude Desktop

**Resources:**
- `clanstvo://clani` – seznam aktivnih članov
- `clanstvo://clani/{id}` – kartica člana (vključno vloge, če obstajajo)
- `clanstvo://dashboard/{leto}` – statistika za leto (agregatne poizvedbe iz v1.25)
- `clanstvo://email-predloge` – razpoložljive predloge (6 privzetih)

**Tools (samo branje):**
- `isci_clane(q)` – iskanje (vzorec iz obstoječega `GET /clani/iskanje` JSON endpointa)
- `neplacniki(leto)` – neplačniki za leto
- `placniki(leto)` – plačniki za leto *(v1.23+)*
- `rd_stanje(v_dneh?)` – veljavnosti RD (privzeto 180 dni)
- `vloge_clanov(naziv?, aktivne?)` – vloge članov *(v1.15+)*

**Ocena dela:** 3–4 dni (več primitiv zaradi vloge in razširjenih filtrov)

---

### Faza 2: Pisalni API endpointi + MCP tools

**Cilj:** AI lahko sproži vnos plačila, pošlje obvestilo, generira/pošlje kartico, posodobi podatke člana.

**Datoteke:**
- `app/routers/api_v1.py` – novi `/api/v1/` endpointi z API ključ auth
- `app/api_auth.py` – Bearer token middleware za API endpointe
- Posodobitev `mcp_server.py` z novimi tools

**Novi endpointi:**
- `POST /api/v1/clanarine` – dodaj plačilo
- `POST /api/v1/aktivnosti` – dodaj aktivnost
- `PATCH /api/v1/clani/{id}` – posodobi podatke
- `POST /api/v1/obvestila/posli` – pošlji obvestilo (bulk filtri: neplacniki, placniki, rd_potekla, rd_kmalu, vsi_aktivni, vsi)
- `GET /api/v1/clani/{id}/kartica/{leto}` – generiraj PDF člansko kartico *(v1.23+)*
- `POST /api/v1/clani/{id}/posli-kartico` – pošlji kartico na email *(v1.23+)*

**Audit log:** vse API akcije zabeležene kot `api_mcp` uporabnik + IP

**Ocena dela:** 4–6 dni (več endpointov zaradi kartic in razširjenih bulk filtrov)

---

### Faza 3 (opcijsko): HTTP transport za oddaljeni dostop

**Cilj:** MCP strežnik dostopen prek HTTPS (ne samo lokalni stdio), kar omogoča integracijo s claude.ai spletno različico ali lastnim AI agentom.

**Zahteve:**
- MCP strežnik kot ločen Docker servis z OAuth 2.1 / API ključ avtentikacijo
- HTTPS prek obstoječega Synology reverse proxy
- Posodobitev `docker-compose.yml`

**Ocena dela:** 5–7 dni (večina časa za OAuth implementacijo)

---

## 10. Ocena obsega dela

| Faza | Obseg | Vrednost | Priporočilo |
|------|-------|----------|-------------|
| Faza 1 – bralni MCP | 3–4 dni | Visoka (poizvedbe, poročila, vloge) | **Implementirati** |
| Faza 2 – pisalni API + MCP | 4–6 dni | Visoka (vnos, pošiljanje, kartice) | Implementirati po Fazi 1 |
| Faza 3 – HTTP transport | 5–7 dni | Nizka (klub = lokalna VPN raba) | Odložiti |

---

## 11. Sklep

MCP integracija ima za to aplikacijo **visoko praktično vrednost** – večina vrednosti je dosegljiva že s Fazo 1 (bralni strežnik), ki je nizko tvegana in kratka za implementacijo.

**Ključne ugotovitve:**

1. **stdio transport** je primeren za radioklubski scenarij (lokalna/VPN raba, Claude Desktop na računalniku tajnika).

2. **Faza 1 (branje)** je optimalen naslednji korak: 3–4 dni dela, nič tveganja, takojšnja vrednost za poizvedbe, poročila in pregled vloge.

3. **Faza 2 (pisanje)** zahteva dodajanje API endpointov – arhitekturno čisto, a zahteva skrb za audit log in varnost. Od v1.23 vključuje tudi generiranje in pošiljanje članskih kartic.

4. **Faza 3 (HTTP)** je nesorazmerno zahtevna glede na predvideno lokalno rabo – odložiti.

5. **Skupna `app/queries.py`** je predpogoj za dolgoročno vzdrževanje – prepreči podvajanje poizvedb med web routerji in MCP strežnikom.

---

*Radio klub S59DGO – MCP analiza, 2026-03-05 (posodobljeno 2026-03-31 za v1.26)*
