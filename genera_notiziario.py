import asyncio
import datetime
import re
import time
import urllib.request
from zoneinfo import ZoneInfo
import edge_tts
import feedparser

# --- CONFIGURAZIONE FONTI LOCALI ---
FEED_URLS = [
    "https://google.com",
    "https://ansa.it",
]

VOCE = "it-IT-DiegoNeural"  # Oppure "it-IT-ElsaNeural" per voce femminile
VELOCITA_VOCE = (
    "+15%"  # Ritmo radiofonico (+15% più veloce rispetto al parlato lento)
)
FILE_OUTPUT = "notiziario.mp3"

# Durata massima desiderata in secondi (90 = 1 minuto e mezzo)
DURATA_MASSIMA_SECONDI = 90
PAROLE_AL_SECONDO = 2.6  # Aggiornato per la nuova velocità di lettura


def pulisci_testo(testo):
  testo = re.sub(r"<[^>]+>", "", testo)
  testo = re.sub(r"\s+", " ", testo).strip()
  return testo


def estrai_ultime_notizie(urls):
  articoli = []
  titoli_visti = set()

  # Simula un browser reale per evitare che Google News o ANSA blocchino GitHub
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
          " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
      )
  }

  for url in urls:
    try:
      req = urllib.request.Request(url, headers=headers)
      with urllib.request.urlopen(req, timeout=15) as response:
        contenuto_xml = response.read()
      feed = feedparser.parse(contenuto_xml)
    except Exception as e:
      print(f"Errore nel caricamento di {url}: {e}")
      continue

    for entry in feed.entries:
      titolo_grezzo = pulisci_testo(entry.title)
      titolo = titolo_grezzo.split(" - ")[0].strip()

      if not titolo or titolo.lower() in titoli_visti:
        continue
      titoli_visti.add(titolo.lower())

      data_pub = getattr(entry, "published_parsed", None)
      timestamp = time.mktime(data_pub) if data_pub else 0

      articoli.append({"titolo": titolo, "timestamp": timestamp})

  articoli.sort(key=lambda x: x["timestamp"], reverse=True)
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

  intro = f"{saluto}. Ecco le ultime notizie locali delle ore {ora_formattata}."
  chiusura = "Il notiziario termina qui. La prossima edizione tra un'ora!"

  parole_massime = int(DURATA_MASSIMA_SECONDI * PAROLE_AL_SECONDO)
  parole_usate = len(intro.split()) + len(chiusura.split())

  copione = [intro]
  notizie_raccolte = 0

  ultime_notizie = estrai_ultime_notizie(FEED_URLS)

  for articolo in ultime_notizie:
    # Rimosso "Notizia:" ripetitivo per un ritmo più scorrevole da vero GR
    frase_notizia = f"{articolo['titolo']}."
    parole_frase = len(frase_notizia.split())

    if parole_usate + parole_frase <= parole_massime:
      copione.append(frase_notizia)
      parole_usate += parole_frase
      notizie_raccolte += 1
    else:
      break

  if notizie_raccolte == 0:
    copione.append("Al momento non ci sono nuovi aggiornamenti.")

  copione.append(chiusura)

  # Unisce le frasi con un solo spazio e a capo: pausa breve e naturale
  testo_finale = "\n".join(copione)
  print(
      f"Notiziario ore {ora_formattata} | Notizie trovate: {notizie_raccolte} |"
      f" Parole: {parole_usate}"
  )
  print("Testo:\n", testo_finale)

  comunicazione = edge_tts.Communicate(
      testo_finale, VOCE, rate=VELOCITA_VOCE
  )
  await comunicazione.save(FILE_OUTPUT)


if __name__ == "__main__":
  asyncio.run(crea_audio())
