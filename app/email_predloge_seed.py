"""Seed privzetih e-poštnih predlog ob zagonu aplikacije."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .models import EmailPredloga


_PREDLOGA_POZIV = """\
<p>Spoštovani {{ priimek }} {{ ime }},</p>

<p>obveščamo vas, da je prišel čas za plačilo članarine za leto <strong>{{ leto }}</strong>.
Prosimo vas, da poravnate obveznost čim prej.</p>

<p>Za enostavno plačilo skenirajte priloženo UPN QR kodo:</p>

<p>{{ qr_koda }}</p>

<p>Hvala za vašo podporo in lep pozdrav,<br>
Uprava kluba</p>
"""

_PREDLOGA_OPOMNIK = """\
<p>Spoštovani {{ priimek }} {{ ime }},</p>

<p>ugotavljamo, da za leto <strong>{{ leto }}</strong> še niste poravnali članarine.
Prosimo, da to storite v najkrajšem možnem času.</p>

<p>Za plačilo skenirajte priloženo UPN QR kodo:</p>

<p>{{ qr_koda }}</p>

<p>V primeru vprašanj nas kontaktirajte.<br>
Lep pozdrav,<br>
Uprava kluba</p>
"""

_PREDLOGA_RD = """\
<p>Spoštovani {{ priimek }} {{ ime }}{% if klicni_znak %} ({{ klicni_znak }}){% endif %},</p>

<p>obveščamo vas, da je {% if veljavnost_rd %}vaše radijsko dovoljenje poteklo dne
<strong>{{ veljavnost_rd }}</strong>{% else %}veljavnost vašega radijskega dovoljenja
potekla oziroma datum ni zabeležen v evidenci{% endif %}.</p>

<p>Prosimo vas, da čim prej uredite podaljšanje dovoljenja pri Agenciji za komunikacijska
omrežja in storitve (AKOS). Brez veljavnega dovoljenja ne smete opravljati
radioamaterske dejavnosti.</p>

<p>Za vse informacije glede postopka podaljšanja obiščite spletno stran AKOS
ali nas kontaktirajte.</p>

<p>Lep pozdrav,<br>
Uprava kluba</p>
"""

_PREDLOGA_PODATKI = """\
<p>Spoštovani {{ priimek }} {{ ime }},</p>

<p>prosimo vas, da preverite vaše podatke, ki jih imamo zabeležene v naši evidenci:</p>

<table style="border-collapse:collapse; width:100%; max-width:500px; font-size:14px;">
  <tr style="background:#f8f9fa;">
    <td style="padding:6px 10px; font-weight:bold; width:45%;">Ime in priimek</td>
    <td style="padding:6px 10px;">{{ ime }} {{ priimek }}</td>
  </tr>
  <tr>
    <td style="padding:6px 10px; font-weight:bold;">Klicni znak</td>
    <td style="padding:6px 10px;">{{ klicni_znak or "–" }}</td>
  </tr>
  <tr style="background:#f8f9fa;">
    <td style="padding:6px 10px; font-weight:bold;">Vrsta članstva</td>
    <td style="padding:6px 10px;">{{ tip_clanstva or "–" }}</td>
  </tr>
  <tr>
    <td style="padding:6px 10px; font-weight:bold;">Operaterski razred</td>
    <td style="padding:6px 10px;">{{ operaterski_razred or "–" }}</td>
  </tr>
  <tr style="background:#f8f9fa;">
    <td style="padding:6px 10px; font-weight:bold;">Naslov</td>
    <td style="padding:6px 10px;">{{ naslov_ulica or "" }}{% if naslov_ulica and naslov_posta %}, {% endif %}{{ naslov_posta or "" }}{% if not naslov_ulica and not naslov_posta %}–{% endif %}</td>
  </tr>
  <tr>
    <td style="padding:6px 10px; font-weight:bold;">Mobilni telefon</td>
    <td style="padding:6px 10px;">{{ mobilni_telefon or "–" }}</td>
  </tr>
  <tr style="background:#f8f9fa;">
    <td style="padding:6px 10px; font-weight:bold;">Telefon (dom)</td>
    <td style="padding:6px 10px;">{{ telefon_doma or "–" }}</td>
  </tr>
  <tr>
    <td style="padding:6px 10px; font-weight:bold;">E-pošta</td>
    <td style="padding:6px 10px;">{{ elektronska_posta or "–" }}</td>
  </tr>
  <tr style="background:#f8f9fa;">
    <td style="padding:6px 10px; font-weight:bold;">Veljavnost RD</td>
    <td style="padding:6px 10px;">{{ veljavnost_rd or "–" }}</td>
  </tr>
  <tr>
    <td style="padding:6px 10px; font-weight:bold;">Št. E.S. kartice</td>
    <td style="padding:6px 10px;">{{ es_stevilka or "–" }}</td>
  </tr>
</table>

<p style="margin-top:16px;">Če kateri od zgornjih podatkov ni pravilen ali je zastarel,
nas prosimo čim prej obvestite, da posodobimo evidenco.</p>

<p>Lep pozdrav,<br>
Uprava kluba</p>
"""

_PREDLOGA_KARTICA = """\
<p>Spoštovani {{ priimek }} {{ ime }},</p>

<p>v priponki najdete vašo <strong>člansko izkaznico za leto {{ leto }}</strong>.</p>

<p>Lep pozdrav,<br>
{{ klub_ime }}</p>
"""

_PREDLOGA_UNIVERZALNA = """\
<p>Spoštovani {{ priimek }} {{ ime }},</p>

<p><!-- Sem vnesite vsebino sporočila. -->
<!-- Razpoložljive spremenljivke: -->
<!-- Osnovne: {{ ime }}, {{ priimek }}, {{ klicni_znak }}, {{ leto }} -->
<!-- Naslov: {{ naslov_ulica }}, {{ naslov_posta }} -->
<!-- Članstvo: {{ tip_clanstva }}, {{ operaterski_razred }}, {{ klicni_znak_nosilci }} -->
<!-- Kontakt: {{ mobilni_telefon }}, {{ telefon_doma }}, {{ elektronska_posta }} -->
<!-- Dovoljenje: {{ veljavnost_rd }} (oblika: DD. MM. LLLL ali prazno) -->
<!-- Ostalo: {{ es_stevilka }}, {{ opombe }} -->
<!-- QR koda: {{ qr_koda }} (HTML <img> tag) -->
</p>

<p>Lep pozdrav,<br>
Uprava kluba</p>
"""


_PRIVZETE_PREDLOGE = [
    {
        "naziv": "Poziv k plačilu članarine",
        "zadeva": "Poziv k plačilu članarine za leto {{ leto }}",
        "telo_html": _PREDLOGA_POZIV,
        "vkljuci_qr": True,
        "prilozi_kartico": False,
    },
    {
        "naziv": "Opomnik za zamudnike",
        "zadeva": "Opomnik – neplačana članarina za leto {{ leto }}",
        "telo_html": _PREDLOGA_OPOMNIK,
        "vkljuci_qr": True,
        "prilozi_kartico": False,
    },
    {
        "naziv": "Potečena veljavnost radijskega dovoljenja",
        "zadeva": "Obvestilo o potečeni veljavnosti radijskega dovoljenja – {{ priimek }} {{ ime }}",
        "telo_html": _PREDLOGA_RD,
        "vkljuci_qr": False,
        "prilozi_kartico": False,
    },
    {
        "naziv": "Potrdi podatke člana",
        "zadeva": "Prosimo preverite vaše podatke v evidenci kluba",
        "telo_html": _PREDLOGA_PODATKI,
        "vkljuci_qr": False,
        "prilozi_kartico": False,
    },
    {
        "naziv": "Pošiljanje članske kartice",
        "zadeva": "Članska izkaznica {{ leto }} – {{ klub_oznaka }}",
        "telo_html": _PREDLOGA_KARTICA,
        "vkljuci_qr": False,
        "prilozi_kartico": True,
    },
    {
        "naziv": "Univerzalna predloga",
        "zadeva": "Obvestilo kluba – {{ priimek }} {{ ime }}",
        "telo_html": _PREDLOGA_UNIVERZALNA,
        "vkljuci_qr": False,
        "prilozi_kartico": False,
    },
]


def seed_predloge(db: Session) -> None:
    """Ustvari privzete predloge, ki še ne obstajajo; posodobi vkljuci_qr in prilozi_kartico."""
    obstoječe = {
        p.naziv: p for p in db.query(EmailPredloga).filter(EmailPredloga.je_privzeta == True).all()
    }
    zdaj = datetime.now(timezone.utc)
    spremenjeno = False
    for p in _PRIVZETE_PREDLOGE:
        if p["naziv"] in obstoječe:
            obstoječe[p["naziv"]].vkljuci_qr = p["vkljuci_qr"]
            obstoječe[p["naziv"]].prilozi_kartico = p["prilozi_kartico"]
            spremenjeno = True
        else:
            db.add(EmailPredloga(
                naziv=p["naziv"],
                zadeva=p["zadeva"],
                telo_html=p["telo_html"],
                je_privzeta=True,
                vkljuci_qr=p["vkljuci_qr"],
                prilozi_kartico=p["prilozi_kartico"],
                created_at=zdaj,
            ))
            spremenjeno = True
    if spremenjeno:
        db.commit()
