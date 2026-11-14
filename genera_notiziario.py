import asyncio
import datetime
import html
import re
import subprocess
from zoneinfo import ZoneInfo
import edge_tts

# --- CONFIGURAZIONE FONTI UFFICIALI ---
FONTI_RSS = [
    "https://" + "www.rainews.it/rss/tutti",
    "https://" + "www.ansa.it/emiliaromagna/notizie/emiliaromagna_rss.xml",
    "https://" + "www.ansa.it/lombardia/notizie/lombardia_rss.xml",
]

VOCE = "it-IT-DiegoNeural"
VELOCITA_VOCE = "+15%"
FILE_OUTPUT = "notiziario.mp3"

# Durata massima in secondi (90s = circa 4-5 notizie complete di riassunto)
DURATA_MASSIMA_SECONDI = 90
PAROLE_AL_SECONDO = 2.7


def pulisci_testo(testo):
  if not testo:
    return ""
  testo = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", testo, flags=re.DOTALL)
  testo = html.unescape(testo)
  testo = re.sub(r"<[^>]+>", "", testo)

  # Uniforma apostrofi e rimuove virgolette che disturbano la voce
  testo = testo.replace("’", "'").replace("‘", "'")
  testo = testo.replace('"', "").replace("“", "").replace("”", "")
  testo = testo.replace("«", "").replace("»", "")
  testo = re.sub(r"(^|\s)'([^']+)'(\s|$|[.,;:!?])", r"\1\2\3", testo)

  # Correzioni fonetiche
  testo = testo.replace("//", " ")
  testo = re.sub(r"\bXi\b", "Sci", testo)
  testo = re.sub(r"\(ANSA\)", "", testo, flags=re.IGNORECASE)

  testo = re.sub(r"\s+", " ", testo).strip()
  return testo


def estrai_ultime_notizie(urls):
  articoli = []
  titoli_visti = set()

  for url in urls:
    try:
      risultato = subprocess.run(
          [
              "curl",
              "-s",
              "-L",
              "--compressed",
              "-A",
              "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0",
              url,
          ],
          capture_output=True,
          text=True,
          timeout=15,
      )
      testo_grezzo = risultato.stdout
      items = re.findall(
          r"<item\b[^>]*>(.*?)</item>", testo_grezzo, flags=re.DOTALL
      )

      for item in items[:4]:
        match_titolo = re.search(
            r"<title\b[^>]*>(.*?)</title>", item, flags=re.DOTALL
        )
        if not match_titolo:
          continue

        titolo = pulisci_testo(match_titolo.group(1)).rstrip(".")
        if not titolo or titolo.lower() in titoli_visti:
          continue

        # Estrae anche il riassunto (<description>) per dare corpo alla notizia
        match_desc = re.search(
            r"<description\b[^>]*>(.*?)</description>", item, flags=re.DOTALL
        )
        descrizione = ""
        if match_desc:
          descrizione = pulisci_testo(match_desc.group(1)).rstrip(".")
          # Evita di ripetere la descrizione se è identica al titolo
          if descrizione.lower().startswith(titolo.lower()):
            descrizione = descrizione[len(titolo) :].lstrip(" .:-").strip()

        titoli_visti.add(titolo.lower())

        if descrizione and len(descrizione) > 15:
          notizia_completa = f"{titolo}. {descrizione}."
        else:
          notizia_completa = f"{titolo}."

        articoli.append(notizia_completa)

    except Exception as e:
      print(f"Errore su {url}: {e}")
      continue

  return articoli


async def crea_audio():
  adesso = datetime.datetime.now(ZoneInfo("Europe/Rome"))

  if adesso.minute >= 30:
    ora_notiziario = (adesso + datetime.timedelta(hours=1)).replace(minute=0)
  else:
    ora_notiziario = adesso.replace(minute=0)

  ora_formattata = ora_notiziario.strftime("%H:%M")
  ora_int = ora_notiziario.hour

  if 5 <= ora_int < 13:
    saluto = "Buongiorno dalla redazione"
  elif 13 <= ora_int < 18:
    saluto = "Buon pomeriggio dalla redazione"
  else:
    saluto = "Buonasera dalla redazione"

  intro = f"{saluto}. Ecco le notizie delle ore {ora_formattata}."
  chiusura = "Il notiziario termina qui, la prossima edizione tra un'ora!"

  parole_massime = int(DURATA_MASSIMA_SECONDI * PAROLE_AL_SECONDO)
  parole_usate = len(intro.split()) + len(chiusura.split())

  copione = [intro]
  notizie_raccolte = 0

  ultime_notizie = estrai_ultime_notizie(FONTI_RSS)

  for notizia in ultime_notizie:
    parole_frase = len(notizia.split())

    if parole_usate + parole_frase <= parole_massime:
      copione.append(notizia)
      parole_usate += parole_frase
      notizie_raccolte += 1
    else:
      break

  if notizie_raccolte == 0:
    copione.append("Al momento non ci sono nuovi aggiornamenti.")

  copione.append(chiusura)

  testo_finale = " ".join(copione)

  print(f"Totale notizie approfondite nel GR: {notizie_raccolte}")
  print("Testo finale:\n", testo_finale)

  comunicazione = edge_tts.Communicate(
      testo_finale, VOCE, rate=VELOCITA_VOCE
  )
  await comunicazione.save(FILE_OUTPUT)


if __name__ == "__main__":
  asyncio.run(crea_audio())
