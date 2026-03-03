"""Seed privzetih e-poštnih predlog ob zagonu aplikacije."""
from datetime import datetime

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


def seed_predloge(db: Session) -> None:
    """Ustvari privzeti predlogi, če tabela še nima nobene predloge."""
    if db.query(EmailPredloga).count() > 0:
        return

    zdaj = datetime.utcnow()
    predloge = [
        EmailPredloga(
            naziv="Poziv k plačilu članarine",
            zadeva="Poziv k plačilu članarine za leto {{ leto }}",
            telo_html=_PREDLOGA_POZIV,
            je_privzeta=True,
            created_at=zdaj,
        ),
        EmailPredloga(
            naziv="Opomnik za zamudnike",
            zadeva="Opomnik – neplačana članarina za leto {{ leto }}",
            telo_html=_PREDLOGA_OPOMNIK,
            je_privzeta=True,
            created_at=zdaj,
        ),
    ]
    db.add_all(predloge)
    db.commit()
