"""compute_gender.py — Pre-compute influencer_gender from name, bio, and audience signals.

Runs the same 3-signal inference used by filter_service but with an expanded name list,
and persists the result in the influencer_gender column so it doesn't need to be
re-inferred on every search query.

Values written: 'male', 'female', or NULL (left unchanged for truly indeterminate profiles).

Usage
-----
    # Preview without writing
    cd backend && python -m app.services.compute_gender --dry-run

    # Populate NULL rows (safe to run repeatedly — idempotent)
    cd backend && python -m app.services.compute_gender

    # Re-classify every row, overwriting existing values
    cd backend && python -m app.services.compute_gender --force
"""

import argparse
import asyncio
import logging
import re
import unicodedata
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Expanded name sets (common Spanish, Catalan, and Latin-American first names)
# ---------------------------------------------------------------------------

_FEMALE_NAMES = {
    # Core Spanish female names
    "maria", "maría", "ana", "elena", "lucia", "lucía", "carmen", "laura",
    "marta", "sara", "paula", "claudia", "andrea", "irene", "alba", "nuria",
    "silvia", "rosa", "isabel", "cristina", "patricia", "eva", "pilar",
    "raquel", "monica", "mónica", "blanca", "beatriz", "sandra", "ines",
    "inés", "julia", "natalia", "alicia", "diana", "carolina", "lola",
    "rocio", "rocío", "marina", "olga", "sonia", "angeles", "ángeles",
    "vanessa", "veronica", "verónica", "susana", "belén", "belen",
    "esther", "teresa", "begoña", "concepcion", "concepción", "jannys",
    "águeda", "agueda", "mariona", "jimena",
    # Additional common names missed from initial list
    "clara", "salma", "ingrid", "martina", "noa", "rebeka",
    "greta", "kira", "vera", "lea", "luna", "ariadna", "miriam",
    "helen", "helena", "isabela", "nadia", "luciana",
    "jenni", "jenny", "vicky", "naty", "bea", "susi", "cris", "isa",
    "lara", "angie", "candela", "arabella", "nieves", "yerlina",
    "nadina", "sandrita", "michelle",
    # Additional Spanish / Latin-American female names
    "sofía", "sofia", "valentina", "camila", "gabriela", "alejandra",
    "lorena", "mar", "aroa", "noelia", "tamara", "lidia", "amparo",
    "dolores", "mercedes", "yolanda", "gemma", "montserrat", "judith",
    "celia", "sheila", "carla", "ainara", "leire", "aitana", "anna",
    "emma", "laia", "núria", "mireia", "meritxell", "anna", "joana",
    "noa", "martina", "emma", "valentina", "lucia", "isabella",
    "daniela", "valeria", "paola", "fernanda", "adriana", "rebeca",
    "rebeka", "berta", "gema", "macarena", "inmaculada", "ainhoa",
    "amaia", "itziar", "garbiñe", "garbiñe", "izaskun", "nerea",
    "naroa", "olatz", "june", "haizea", "ane", "miren", "amaia",
    "nekane", "maider", "uxue", "iratxe", "idoia", "eider",
    # Catalan female names
    "montse", "laia", "júlia", "mar", "mercè", "roser", "núria",
    "carme", "dolors", "pilar", "rosa", "miriam",
    # International names common in Spain
    "jessica", "jennifer", "stephanie", "natalie", "samantha",
    "amanda", "ashley", "brittany", "kayla", "madison", "taylor",
    "victoria", "alexandra", "stephanie", "deborah", "lisa",
    # Additional names found missing from DB analysis (Feb 2026)
    "aida", "elsa", "carlota", "nicole", "paloma", "judit", "lydia",
    "elisa", "carol", "arantxa", "ester", "martita", "gisela",
    "antonella", "anabel", "fanny", "yvonne", "maribel", "adara",
    "leena", "leena", "izzy",
}

_MALE_NAMES = {
    # Core Spanish male names
    "carlos", "david", "javier", "daniel", "jose", "josé", "miguel",
    "antonio", "francisco", "manuel", "pedro", "alejandro", "rafael",
    "fernando", "pablo", "sergio", "jorge", "alberto", "angel", "ángel",
    "luis", "ramon", "ramón", "juan", "diego", "victor", "víctor",
    "enrique", "roberto", "marcos", "mario", "ivan", "iván", "adrian",
    "adrián", "oscar", "óscar", "santiago", "andres", "andrés", "raul",
    "raúl", "hugo", "alejo", "facundo", "israel", "caio", "ren",
    # Additional Spanish / Latin-American male names
    "ignacio", "gonzalo", "borja", "nacho", "álvaro", "alvaro",
    "emilio", "ernesto", "curro", "paco", "tomás", "tomas",
    "nicolás", "nicolas", "jaime", "guillermo", "rodrigo", "arturo",
    "esteban", "gerardo", "gustavo", "hector", "héctor", "joaquin",
    "joaquín", "leonel", "lucas", "mateo", "máximo", "maximo",
    "nicolás", "omar", "ricardo", "rubén", "ruben", "salvador",
    "sebastián", "sebastian", "valentín", "valentin", "xavier",
    "fernando", "félix", "felix", "german", "germán", "héctor",
    "horacio", "leandro", "marcelo", "mauricio", "maximiliano",
    "renato", "rodrigo", "rolando", "ronaldo", "silvio", "teodoro",
    "tobias", "tobías", "ulises", "valentín",
    # Catalan male names
    "gerard", "marc", "eric", "pol", "arnau", "quim", "guillem",
    "pau", "xavi", "sergi", "joan", "jordi", "miquel", "ricard",
    "ferran", "oriol", "bernat", "xavier", "pere", "lluís", "lluis",
    "carles", "francesc", "albert", "robert", "enric", "ramon",
    "aleix", "biel", "martí", "nil", "jan", "aniol",
    # Basque male names
    "iker", "unai", "asier", "aitor", "gorka", "mikel", "julen",
    "andoni", "iñaki", "inaki", "aritz", "ibai", "beñat", "gaizka",
    "ander", "oier", "xabier", "koldo", "joseba", "urko",
    # International names common in Spain
    "alex", "chris", "ryan", "jason", "kevin", "brian", "brandon",
    "nicholas", "matthew", "joshua", "anthony", "andrew", "christopher",
    "michael", "james", "robert", "william", "richard", "charles",
    "thomas", "mark", "donald", "steven", "edward", "george",
    # Spanish nickname forms and shortenings missing from initial list (Feb 2026)
    "aaron", "aarón", "willy", "fran", "jesus", "jesús", "manu",
    "rafa", "edu", "leo", "kike", "javi", "pepe", "jon",
    "julio", "gabriel", "toni", "ramiro", "alfonso", "frank",
    "christian", "michel", "mauro", "gianluca", "adam", "felipe",
    "moha", "curro", "nacho", "paco", "santi", "xavi", "nando",
    "vito", "miki", "toño",
}

_FEMALE_BIO_SIGNALS = {
    "she/her", "ella", "mamá", "madre", "actriz", "escritora",
    "maquilladora", "creadora", "influencer mujer", "blogger",
    "fotógrafa", "diseñadora", "periodista", "profesora",
    "enfermera", "psicóloga", "nutricionista", "bailarina",
    "cantante", "presentadora", "modelo femenina", "mujer",
}

_MALE_BIO_SIGNALS = {
    "he/him", "él", "papá", "padre", "actor", "escritor",
    "creador", "fotógrafo", "diseñador", "periodista",
    "profesor", "enfermero", "psicólogo", "nutricionista",
    "bailarín", "cantante", "presentador", "modelo masculino",
}

# Strip these emoji chars from the start of first words
_EMOJI_STRIP = '✖️💀🧸☠️👑🌸🌺💫✨🔥🎯🏆💪🎤🎬📸🎮🎵🌟⭐🏅🎁💡🔑❤️💙💚💛🧡💜🖤🤍🤎'


def _infer_gender(
    display_name: Optional[str],
    bio: Optional[str],
    audience_genders: Optional[dict],
    username: Optional[str] = None,
) -> Optional[str]:
    """Return 'male', 'female', or None (indeterminate).

    Same priority order as filter_service._infer_influencer_gender() but uses
    the expanded name lists defined in this module.
    """
    # Signal 1: audience_genders inverse heuristic
    if audience_genders:
        male_pct = audience_genders.get("male", audience_genders.get("Male", 0))
        female_pct = audience_genders.get("female", audience_genders.get("Female", 0))
        if male_pct > 65:
            return "female"
        if female_pct > 65:
            return "male"

    # Signal 2: bio keyword scan
    bio_lower = (bio or "").lower()
    if bio_lower:
        for signal in _FEMALE_BIO_SIGNALS:
            if signal in bio_lower:
                return "female"
        for signal in _MALE_BIO_SIGNALS:
            if signal in bio_lower:
                return "male"

    # Signal 3: display name first-word matching
    if display_name:
        # Normalize Unicode fancy fonts (mathematical bold/italic/monospace etc.)
        display_name = unicodedata.normalize('NFKC', display_name)
        first_word = re.split(r'[\s|·•\-_]+', display_name.strip())[0].lower()
        first_word = first_word.strip(_EMOJI_STRIP)
        if first_word in _FEMALE_NAMES:
            return "female"
        if first_word in _MALE_NAMES:
            return "male"

    # Signal 3b: username first segment (split by _ or digits) as fallback
    if username:
        # Strip leading/trailing underscores before splitting
        first_seg = re.split(r'[_\d]', username.strip().strip('_'))[0].lower()
        if len(first_seg) >= 3:
            if first_seg in _FEMALE_NAMES:
                return "female"
            if first_seg in _MALE_NAMES:
                return "male"
            # Prefix match: "kirahuberman" → startswith "kira"
            for name in _FEMALE_NAMES:
                if len(name) >= 4 and first_seg.startswith(name):
                    return "female"
            for name in _MALE_NAMES:
                if len(name) >= 4 and first_seg.startswith(name):
                    return "male"

    return None


async def compute_gender(dry_run: bool = False, force: bool = False) -> None:
    from app.config import get_settings
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    mode = "DRY RUN — " if dry_run else ""
    print(f"{mode}Computing influencer_gender from name/bio/audience signals…")
    if force:
        print("  --force: re-classifying ALL influencers (including those already classified)")

    async with async_session() as session:
        # Fetch rows to classify
        if force:
            rows = await session.execute(
                text("SELECT id, username, display_name, bio, audience_genders FROM influencers")
            )
        else:
            rows = await session.execute(
                text(
                    "SELECT id, username, display_name, bio, audience_genders "
                    "FROM influencers WHERE influencer_gender IS NULL"
                )
            )
        rows = rows.fetchall()

        counts = {"female": 0, "male": 0, "unknown": 0, "total": len(rows)}
        print(f"  Processing {len(rows)} influencer(s)…")

        for row in rows:
            uid, username, display_name, bio, audience_genders = row
            gender = _infer_gender(display_name, bio, audience_genders, username)

            if gender:
                counts[gender] += 1
            else:
                counts["unknown"] += 1

            if not dry_run and gender:
                await session.execute(
                    text(
                        "UPDATE influencers SET influencer_gender = :gender WHERE id = :id"
                    ),
                    {"gender": gender, "id": uid},
                )

        if not dry_run:
            await session.commit()

    await engine.dispose()

    print(
        f"\n{'(dry run) ' if dry_run else ''}Results:"
        f"\n  female  : {counts['female']:>6}"
        f"\n  male    : {counts['male']:>6}"
        f"\n  unknown : {counts['unknown']:>6}"
        f"\n  total   : {counts['total']:>6}"
    )
    if dry_run:
        print("\nNo changes written. Remove --dry-run to apply.")
    else:
        print(
            f"\nDone — influencer_gender populated for "
            f"{counts['female'] + counts['male']} of {counts['total']} influencers."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pre-compute influencer_gender column.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview results without writing to DB",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-classify all influencers, overwriting existing values",
    )
    args = parser.parse_args()
    asyncio.run(compute_gender(dry_run=args.dry_run, force=args.force))
