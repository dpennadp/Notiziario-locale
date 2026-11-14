import asyncio
import datetime
import re
import time
from zoneinfo import ZoneInfo
import edge_tts
import feedparser

# --- CONFIGURAZIONE FONTI LOCALI (Brescia e Lombardia) ---
FEED_URLS = [
    "https://google.com",
    "https://ansa.it",
]

VOCE = "it-IT-DiegoNeural"  # Oppure "it-IT-ElsaNeural" per voce femminile
FILE_OUTPUT = "notiziario.mp3"

# Durata massima desiderata in secondi (90 = 1 minuto e mezzo)
DURATA_MASSIMA_SECONDI = 120
PAROLE_AL_SECONDO = 2.3


def pulisci_testo(testo):
  testo = re.sub(r"<[^>]+>", "", testo)
  testo = re.sub(r"\s+", " ", testo).strip()
  return testo


def estrai_ultime_notizie(urls):
  articoli = []
  titoli_visti = set()

  for url in urls:
    feed = feedparser.parse(url)
    for entry in feed.entries:
      titolo_grezzo = pulisci_testo(entry.title)
      titolo = titolo_grezzo.split(" - ")[0].strip()

      if titolo.lower() in titoli_visti:
        continue
      titoli_visti.add(titolo.lower())

      data_pub = getattr(entry, "published_parsed", None)
      timestamp = time.mktime(data_pub) if data_pub else 0

      articoli.append({"titolo": titolo, "timestamp": timestamp})

  articoli.sort(key=lambda x: x["timestamp"], reverse=True)
  return articoli


async def crea_audio():
  adesso = datetime.datetime.now(ZoneInfo("Europe/Rome"))

  # Calcola l'ora piena di riferimento (se siamo oltre il minuto 30, arrotonda all'ora successiva)
  if adesso.minute >= 30:
    ora_notiziario = (adesso + datetime.timedelta(hours=1)).replace(minute=0)
  else:
    ora_notiziario = adesso.replace(minute=0)

  ora_formattata = ora_notiziario.strftime("%H:%M")
  ora_int = ora_notiziario.hour

  # Saluto dinamico in base all'ora dell'edizione
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
    frase_notizia = f"Notizia: {articolo['titolo']}."
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

  testo_finale = " ... ".join(copione)
  print(f"Notiziario ore {ora_formattata} | Parole: {parole_usate}")
  print("Testo:\n", testo_finale)

  comunicazione = edge_tts.Communicate(testo_finale, VOCE)
  await comunicazione.save(FILE_OUTPUT)


if __name__ == "__main__":
  asyncio.run(crea_audio())
