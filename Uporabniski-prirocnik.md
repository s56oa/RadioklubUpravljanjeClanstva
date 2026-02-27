# Uporabniški priročnik – Radio klub Člani

*Različica 1.14 | Datum: 2026-02-27*

---

## Kazalo

1. [Uvod](#1-uvod)
2. [Vloge in pravice](#2-vloge-in-pravice)
3. [Prijava in odjava](#3-prijava-in-odjava)
4. [Seznam članov](#4-seznam-članov)
5. [Kartica člana](#5-kartica-člana)
6. [Dodajanje in urejanje člana](#6-dodajanje-in-urejanje-člana)
7. [Evidenca plačil članarine](#7-evidenca-plačil-članarine)
8. [Evidenca aktivnosti](#8-evidenca-aktivnosti)
9. [Skupinsko upravljanje](#9-skupinsko-upravljanje)
10. [Uvoz podatkov iz Excel](#10-uvoz-podatkov-iz-excel)
11. [Izvoz podatkov](#11-izvoz-podatkov)
12. [Nastavitve kluba](#12-nastavitve-kluba)
13. [Upravljanje uporabnikov](#13-upravljanje-uporabnikov)
14. [Dnevnik sprememb (Audit log)](#14-dnevnik-sprememb-audit-log)
15. [Moj profil, geslo in 2FA](#15-moj-profil-geslo-in-2fa)
16. [Statistični dashboard](#16-statistični-dashboard)

---

## 1. Uvod

Aplikacija za upravljanje članstva radiokluba omogoča:

- vodenje evidence vseh članov z njihovimi kontaktnimi podatki in licenčnimi podatki,
- beleženje plačil članarine po posameznih letih,
- beleženje aktivnosti in delovnih ur posameznih članov,
- razvrščanje članov v interesne skupine,
- uvoz obstoječih podatkov iz Excel datoteke in izvoz za prijavo na ZRS (Zveza radioamaterjev Slovenije),
- varno upravljanje z vlogami: vsak uporabnik vidi ali ureja samo tisto, do česar je pooblaščen.

Aplikacija deluje v brskalniku. Ne zahteva namestitve posebne programske opreme na računalnik.

---

## 2. Vloge in pravice

| Vloga | Ogled | Urejanje | Brisanje | Uvoz/Izvoz | Nastavitve | Uporabniki | Audit log |
|-------|-------|----------|----------|------------|------------|------------|-----------|
| **admin** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **urednik** | ✅ | ✅ | ❌ | ✅ (samo izvoz) | ❌ | ❌ | ❌ |
| **bralec** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

> **Opomba:** Urednik lahko dodaja in ureja člane ter beleži plačila in aktivnosti, ne more pa brisati članov, upravljati s skupinami ali dostopati do sistemskih nastavitev.

---

## 3. Prijava in odjava

### Prijava

1. V brskalniku odprite naslov aplikacije (npr. `http://192.168.1.100:8000`).
2. Vnesite **uporabniško ime** in **geslo**.
3. Kliknite **Prijava**.

Ob napačnih podatkih se prikaže sporočilo o napaki. Po 10 zaporednih neuspešnih poskusih z istega naslova je prijava blokirana za 15 minut.

### Prijava z dvostopenjsko avtentikacijo (2FA)

Če imate aktivirano 2FA, se po vnosu gesla prikaže dodaten korak:

1. Odprite aplikacijo za avtentikacijo na vašem mobilnem telefonu (Google Authenticator, Aegis, …).
2. Odčitajte **6-mestno kodo** za ta račun.
3. Vnesite kodo v polje **Koda** in kliknite **Potrdi**.
4. Koda je veljavna 30 sekund – če poteče med vnosom, počakajte naslednjo.

#### Zapomni si napravo (30 dni)

Na strani z vnosom OTP kode je možnost **Zapomni si to napravo (30 dni)**. Če jo označite:
- Aplikacija shrani varni žeton v brskalnik (httponly piškotek).
- Na tej napravi naslednje 30 dni po vpisu gesla **ne boste morali vnašati OTP kode**.
- Na vaši profilni strani vidite seznam zaupljivih naprav in jih lahko kadar koli prekličete.

> Zaupljivo napravo shranite samo na lastnih napravah – **ne na skupnih ali javnih računalnikih.**

Za preklic prijave kliknite **Prekliči prijavo** (vrnete se na prijavno stran, seja se počisti).

### Odjava

Kliknite na svoje ime v zgornjem desnem kotu navigacijske vrstice, nato izberite **Odjava**.

Seja samodejno poteče po 30 minutah neaktivnosti.

---

## 4. Seznam članov

Po prijavi se odpre seznam vseh članov kluba.

### Iskanje in filtriranje

- **Iskalno polje** (zgoraj desno v tabeli): iščite po priimku, imenu, klicnem znaku ali tipu članstva.
- **Filter veljavnosti RD** (zgoraj levo):
  - *Vsi* – prikaže vse člane
  - *Potekla RD* – člani katerih radioamaterska dovoljenje je že poteklo
  - *RD kmalu poteče* – poteče v naslednjih 180 dneh
  - *Veljavna RD* – dovoljenje je veljavno
  - *Brez RD* – ni datuma veljavnosti
- **Filter tipa** (spustni seznam): omeji prikaz na izbrani tip članstva.
- **Leto čl.** (spustni seznam): izberite leto za prikaz stanja plačila članarine. Privzeto je tekoče leto. Ob spremembi leta se seznam samodejno osveži.
- **Stanje čl.**: filtrirajte po plačanem/neplačanem statusu za izbrano leto.

### Stolpci tabele

| Stolpec | Opis |
|---------|------|
| Priimek in ime | Ime člana, klikabilno za odprtje kartice |
| Klicni znak | Radioamaterski klicni znak |
| Tip | Tip članstva (Osebni, Družinski, itd.) |
| Razred | Operaterski razred (A, N) |
| Veljavnost RD | Datum poteka radioamaterskega dovoljenja z barvno oznako |
| Članarina | Status plačila za izbrano leto |
| Akcije | Gumbi za urejanje in brisanje (samo admin) |

### Barvne oznake veljavnosti RD

- **zelena** – dovoljenje je veljavno
- **rumena** – poteče v 180 dneh
- **rdeča** – že poteklo
- *brez oznake* – datum ni vnesen

---

## 5. Kartica člana

Kliknite na ime člana v seznamu, da odprete kartico z vsemi podatki.

Kartica vsebuje:

- **Osnovni podatki**: ime, priimek, klicni znak, naslov, tip, operaterski razred, kontakti, ES-številka, RD veljavnost, soglasje OP, izjava.
- **Skupinske oznake**: modri značkasti gumbi z imeni skupin, ki jim član pripada (klik odpre skupino).
- **Evidenca plačil**: tabela plačil po letih z datumom, zneskom in opombami.
- **Evidenca aktivnosti**: tabela aktivnosti po letih z opisom in delovnimi urami.

### Filter prikazanih let

Nad tabelami plačil in aktivnosti je filter z možnostmi:
- *Vse* – prikaže vse vnose
- *Zadnji 2 leti* – prikaže samo tekoče in preteklo leto
- *Zadnjih 10 let* – prikaže zadnje desetletje

---

## 6. Dodajanje in urejanje člana

### Dodajanje novega člana

1. Na seznamu članov kliknite gumb **+ Nov član** (zgoraj desno).
2. Izpolnite obrazec:
   - **Priimek** in **Ime** sta obvezna. Vnesete jih v katerikoli obliki (aplikacija samodejno normalizira v Title Case).
   - **Klicni znak** se samodejno pretvori v velike črke.
   - **Tip članstva**: izberite iz spustnega seznama.
   - **Veljavnost RD**: datum v obliki LLLL-MM-DD ali izberite iz datumskega izbirnika.
3. Kliknite **Shrani**.

> Za **Družinsko** članstvo se prikaže dodatno polje *Klicni znak nosilci* za vnos klicnih znakov članov, ki so nosilci tega članstva.

### Urejanje obstoječega člana

Na kartici člana kliknite gumb **Uredi** (svinčnik). Vsi podatki se naložijo v obrazec. Spremenite željene vrednosti in kliknite **Shrani**.

### Brisanje člana

Samo admin: na kartici ali v seznamu kliknite gumb **Izbriši** (košček). Potrdite brisanje v pojavnem oknu. Brisanje je **trajno** – skupaj se izbrišejo vsa plačila in aktivnosti tega člana.

---

## 7. Evidenca plačil članarine

Na kartici člana se nahaja sekcija **Evidenca plačil**.

### Beleženje plačila

1. V sekciji *Evidenca plačil* izberite **leto**, vnesite **datum plačila**, po želji **znesek** in **opombe**.
2. Kliknite **Zabeleži plačilo**.

Za vsako leto je dovoljeno **en vnos** – če za izbrano leto plačilo že obstaja, se vnos posodobi (upsert).

### Brisanje plačila

Kliknite gumb **X** ob vnosi v tabeli. Potrdite brisanje.

### Seštevki plačil

Na strani **Izvoz/Uvoz** je razdelek *Seštevki plačil po letu*, kjer je za vsako leto prikazano:
- število plačnikov,
- skupni zbrani znesek (€),
- število vnosov brez znesca.

### Pregled vseh plačil (/clanarine)

V navigacijski vrstici kliknite **Plačila** za zbrani pregled vseh plačil vseh članov.

Filtri (gumbi v vrstici):
- **Trenutno leto** – privzeto, prikaže samo tekoče leto
- **Zadnji 2 leti** – tekoče in preteklo leto
- **Zadnjih 10 let** – zadnje desetletje
- **Vse** – vsi vnosi brez časovnega omejevanja

Nad tabelo se prikažejo **kartice s seštevki po letu**: število plačil in skupni znesek v € za vsako prikazano leto.

---

## 8. Evidenca aktivnosti

Na kartici člana se pod plačili nahaja modra sekcija **Evidenca aktivnosti**.

### Dodajanje aktivnosti

1. Vnesite **leto**, po želji **datum** (ni obvezno), **opis** aktivnosti (do 1000 znakov) in **delovne ure** (decimalno število).
2. Kliknite **Dodaj**.

Za vsako leto je dovoljeno **neomejeno število vnosov**.

### Brisanje aktivnosti

Kliknite gumb **Odstrani** ob vnosu. Brisanje je takojšnje brez ponovnega potrjevanja.

### Pregled vseh aktivnosti (/aktivnosti)

V navigacijski vrstici kliknite **Aktivnosti** za zbrani pregled aktivnosti vseh članov.

Filtri (gumbi v vrstici):
- **Trenutno leto** – privzeto, prikaže samo tekoče leto
- **Zadnji 2 leti** – tekoče in preteklo leto
- **Zadnjih 10 let** – zadnje desetletje
- **Vse** – vsi vnosi brez časovnega omejevanja

V nogi tabele je prikazan **seštevek delovnih ur** za prikazano obdobje.

---

## 9. Skupinsko upravljanje

Skupinsko upravljanje omogoča razvrščanje članov v tematske ali organizacijske skupine (npr. *Odbor*, *Tekmovalci*, *Instruktorji*).

### Pregled skupin

V navigacijski vrstici kliknite **Skupine**. Prikaže se kartična stran z vsemi skupinami in številom članov.

### Ustvarjanje nove skupine

1. Na strani Skupine kliknite **+ Nova skupina**.
2. Vnesite **ime** in po želji **opis**.
3. Kliknite **Shrani**.

### Urejanje in brisanje skupin

Na kartici skupiine kliknite **Uredi skupino** za spremembo imena/opisa ali **Izbriši skupino** za trajno brisanje (samo urednik ali admin).

### Dodajanje/odstranjevanje člana iz skupine

Na kartici skupinne poiščite člana v iskalnem polju in kliknite **+ Dodaj**. Za odstranitev kliknite **Odstrani** ob imenu člana.

---

## 10. Uvoz podatkov iz Excel

Uvoz omogoča masovni prenos podatkov o članih in plačilih iz obstoječe Excel datoteke (.xlsx).

### Priprava Excel datoteke

Excel datoteka mora vsebovati list z besedo **Lista** ali **ListaVsi** v imenu. Prva vrstica mora biti glava s imenovanimi stolpci (npr. *Priimek*, *Ime*, *Klicni znak*, *Tip članstva*, *Veljavnost*, *2025* itd.).

Natančna imena stolpcev so nastavljiva v sekciji **Nastavitve uvoza** na strani Uvoz iz Excel (samo admin).

### Potek uvoza (2 koraka)

**1. korak – Nalaganje in predogled:**

1. V navigaciji kliknite **Izvoz/Uvoz** → **Uvozi iz Excel**.
2. Izberite `.xlsx` datoteko (max. 10 MB).
3. Kliknite **Predogled uvoza**.

Aplikacija parsira datoteko in prikaže:
- **Novi člani** – ki še ne obstajajo v bazi (po priimku in imenu).
- **Preskočeni duplikati** – ki že obstajajo.

**2. korak – Potrditev:**

Preglejte seznam novih članov in kliknite **Potrdi uvoz**. Za preklic kliknite **Prekliči** (datoteka se zavrže, v bazo se nič ne zapiše).

### Kaj se uvozi

Za vsakega novega člana:
- vsi razpoložljivi podatki (naslov, klicni znak, tip, razred, kontakti, soglasje, veljavnost RD, ES-številka, opombe).

Obstoječi člani se ne posodabljajo – pri ponovnem uvozu istega člana se vnos preskoči.

> **Uvoz plačil** je ločen postopek (gumb *Uvozi plačila iz Excel* nižje na isti strani).

### Nastavitev imen stolpcev

Admin: Odprite **Izvoz / Uvoz → Uvozi iz Excel**. Na desni strani strani se prikaže kartica **Nastavitve uvoza**. Za vsako polje vnesite ime stolpca, kot se pojavi v Excel datoteki. Za več možnih imen jih ločite z vejico:

```
priimek, last name, surname
```

Iskanje ni občutljivo na velikost črk in podpira delno ujemanje (iščemo celotne besede v imenu stolpca).

Kliknite **Shrani nastavitve uvoza** za potrditev.

---

## 11. Izvoz podatkov

Dostopno prek navigacije: **Izvoz/Uvoz**.

### Izvoz za ZRS (Zveza radioamaterjev Slovenije)

Ustvari Excel datoteko v formatu za uradno prijavo članov na ZRS.

1. Izberite **leto** v obrazcu.
2. Kliknite **Prenesi ZRS Excel**.

V izvozu so samo aktivni člani, ki so plačali za izbrano leto in katerih tip členstva je vključen v izvoz. Datoteka se poimenuje `prijava_clanov_LLLL_OZNAKA.xlsx`.

**Nastavitve ZRS izvoza (samo admin):** Pod gumbom za prenos je razdelek *Nastavitve izvoza* (razprostirliv). Tam nastavite:
- **Uppercase** – ali se vsa besedilna polja pretvorijo v VELIKE ČRKE.
- **Mapiranje tipov** – kateri interni tip se v izvozu prikaže pod katerim imenom in kateri so izključeni (prazno polje = izključi).
- **Mapiranje operaterskih razredov** – prevod internih oznak v nazive za ZRS.
- **Stolpci** – naziv, vrstni red in ali je posamezni stolpec vključen v datoteko.

### Excel backup

Ustvari backup vseh podatkov v treh listih:
- **Clani** – vsi podatki o članih,
- **Clanarine** – vsa plačila po članih in letih,
- **Aktivnosti** – vse aktivnosti z delovnimi urami.

Kliknite **Prenesi Excel backup**.

### SQLite backup (samo admin)

Prenese surovo datoteko baze podatkov (`clanstvo.db`). Primerno za arhiviranje ali prenos na drug strežnik.

Kliknite **Prenesi SQLite backup**.

---

## 12. Nastavitve kluba

Dostopno samo za admin: navigacija → **Nastavitve**.

### Podatki kluba

Vnesite uradne podatke kluba, ki se izpišejo v navigacijski vrstici in vključijo v ZRS izvozno datoteko:

| Polje | Opis |
|-------|------|
| Ime kluba | Polno uradno ime kluba |
| Klicni znak / oznaka | Klicni znak kluba (prikazano v navigacijski vrstici) |
| Naslov | Ulica in hišna številka |
| Poštna številka in kraj | |
| E-poštni naslov | Kontaktni e-poštni naslov kluba |

> Klicni znak in ime kluba se takoj prikažeta v navigacijski vrstici in na prijavni strani.

### Tipi članstva in operaterski razredi

Prilagodite sezname vrednosti, ki se pojavljajo v spustnih menijih pri vnosu in urejanju članov. Vsako vrednost vpišite v svojo vrstico.

**Privzeti tipi članstva:** Osebni, Družinski, Simpatizerji, Mladi, Invalid

**Privzeti operaterski razredi:** A, N, A - CW, N - CW

Spremembe uveljavite s klikom **Shrani nastavitve**.

---

## 13. Upravljanje uporabnikov

Dostopno samo za admin: navigacija → **Uporabniki**.

### Seznam uporabnikov

Prikazani so vsi uporabniki z vlogo in statusom (aktiven/neaktiven).

### Dodajanje novega uporabnika

1. Kliknite **+ Nov uporabnik**.
2. Vnesite **uporabniško ime**, **geslo** (min. 14 znakov, zahteva velike in male črke, številko in posebni znak), izberite **vlogo** in **ime**.
3. Kliknite **Shrani**.

### Urejanje in deaktivacija

Kliknite **Uredi** ob uporabniku. Spremenite ime, geslo ali vlogo. Polje *Aktiven* omogoča začasno blokado dostopa brez brisanja računa.

### Ponastavitev gesla

Kliknite **Ponastavi geslo**. Aplikacija ustvari začasno 16-znakovno geslo in ga prikaže enkrat (shranjeno je samo v šifrirani obliki). Začasno geslo takoj sporočite uporabniku – ta ga mora ob naslednji prijavi zamenjati prek **Moj profil**.

> Admin ne more videti gesel. Gesla so shranjena samo v obliki bcrypt zgoščene vrednosti.

---

## 14. Dnevnik sprememb (Audit log)

Dostopno samo za admin: navigacija → **Audit log**.

Prikazuje kronološki dnevnik vseh akcij v sistemu (zadnjih 500 vnosov):

| Stolpec | Opis |
|---------|------|
| Čas | Datum in ura akcije |
| Uporabnik | Uporabniško ime |
| IP | IP naslov računalnika |
| Akcija | Vrsta dejanja |
| Opis | Podrobnosti |

### Filtri

S spustnim seznamom **Akcija** filtrirajte po vrsti dejanja:

| Akcija | Opis |
|--------|------|
| `login_ok` | Uspešna prijava (z geslom ali po 2FA koraku) |
| `login_fail` | Neuspešna prijava |
| `login_2fa_caka` | Geslo pravilno, čakanje na OTP kodo |
| `login_2fa_napaka` | Napačna OTP koda pri prijavi |
| `login_2fa_zaupljiva` | Prijava preskočila 2FA prek zaupljive naprave |
| `login_2fa_zaupljiva_nova` | Nova zaupljiva naprava shranjena po uspešni 2FA |
| `logout` | Odjava |
| `clan_ogled` | Ogled kartice člana |
| `clan_dodan` | Dodan novi član |
| `clan_urejen` | Urejeni podatki člana |
| `clan_izbrisan` | Izbrisan član |
| `uvoz_clanov` | Uvoz iz Excel |
| `izvoz_zrs` | ZRS Excel izvoz |
| `izvoz_backup_excel` | Excel backup |
| `izvoz_backup_db` | SQLite backup |
| `2fa_aktivirana` | Uporabnik je aktiviral dvostopenjsko avtentikacijo |
| `2fa_onemogocena` | Uporabnik je onemogočil dvostopenjsko avtentikacijo |

### Izvoz dnevnika

Kliknite **Izvozi Excel** za prenos celotnega dnevnika v obliki Excel datoteke.

---

## 15. Moj profil, geslo in 2FA

Dostopno vsem vlogam: klik na ime v navigacijski vrstici → **Moj profil**.

### Sprememba prikaznega imena

Vnesite novo prikazno ime (polno ime in priimek) in kliknite **Shrani ime**.

### Sprememba gesla

1. Vnesite **trenutno geslo**.
2. Vnesite **novo geslo** (min. 14 znakov, zahteva male in velike črke, številko, posebni znak).
3. Ponovite novo geslo.
4. Kliknite **Zamenjaj geslo**.

> Geslo zamenjajte takoj, ko prejmete začasno geslo od administratorja.

### Dvostopenjska avtentikacija (2FA)

Na profilni strani je razdelek **Dvostopenjska avtentikacija (2FA)**, ki kaže trenutno stanje.

#### Aktivacija 2FA

1. Kliknite gumb **Aktiviraj 2FA**.
2. Na napravi odprite aplikacijo za avtentikacijo in skenirajte prikazano QR kodo.
   - Če QR kode ne morete skenirati, razširite razdelek **Ročni vnos skrivnosti** in ročno vnesite prikazani niz v aplikacijo.
3. Vnesite 6-mestno kodo, ki jo prikaže aplikacija, in kliknite **Potrdi in aktiviraj**.
4. Ob uspešni aktivaciji se vrnete na profilno stran z obvestilom o uspehu.

> Po aktivaciji boste pri vsaki naslednji prijavi morali vnesti kodo iz aplikacije za avtentikacijo.

#### Onemogočanje 2FA

1. V razdelku 2FA vnesite 6-mestno kodo iz vaše aplikacije za avtentikacijo.
2. Kliknite **Onemogoči 2FA**.
3. Ob uspešni deaktivaciji se prikaže obvestilo. Vse zaupljive naprave se samodejno prekličejo.

> Za onemogočanje je potrebna veljavna koda – gesla ni treba vnašati.

#### Zaupljive naprave

Ko je 2FA aktivirana, se pod statusom prikaže seznam shranjenih zaupljivih naprav z:
- datumom shranitve,
- skrajšanim opisom brskalnika/naprave (User-Agent).

Z gumbom **Odjavi vse naprave** prekličete vse shranjene žetone naenkrat. Ob naslednji prijavi boste morali znova vnesti OTP kodo.

---

---

## 16. Statistični dashboard

Dostopno vsem prijavljenim: navigacija → **Dashboard**.

Prikazuje statistični pregled stanja kluba za hitro obvladovanje situacije.

### Stat kartice

Šest kartic v zgornjem delu prikazuje ključne številke za **tekoče leto**:

| Kartica | Opis |
|---------|------|
| Aktivni člani | Število aktivnih članov |
| Vsi člani | Skupno število vseh članov (aktivnih + neaktivnih) |
| Plačalo *leto* | Število aktivnih članov ki so plačali članarino |
| Neplačalo *leto* | Aktivni člani ki še niso plačali |
| Aktivnosti *leto* | Število evidentiranih aktivnosti v tekočem letu |
| Del. ure *leto* | Skupne delovne ure v tekočem letu |

### Grafi

Trije interaktivni grafi prikazujejo podatke za **zadnjih 10 let**:

1. **Plačila članarine po letu** – stolpčni grafikon s številom plačil za vsako leto
2. **Tipi članstva** – tortni grafikon z razporeditvijo aktivnih članov po tipu
3. **Delovne ure po letu** – stolpčni grafikon s skupnimi delovnimi urami

> Grafi se naložijo iz CDN (Chart.js) – za prikaz je potrebna internetna povezava.

---

*Radio klub Člani – Upravljanje Članstva – različica 1.14 (2026-02-27)*
