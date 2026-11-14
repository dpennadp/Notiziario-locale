import asyncio
import datetime
import html
import re
import time
import urllib.request
from zoneinfo import ZoneInfo
import edge_tts
import feedparser

# --- CONFIGURAZIONE FONTI LOCALI DIRETTE ---
FEED_URLS = [
    # Fonti Piacenza e Emilia-Romagna
    "https://liberta.it",
    "https://piacenzasera.it",
    "https://ansa.it",
    # Se preferisci Brescia e Lombardia, metti # davanti alle 3 righe sopra e toglilo qui sotto:
    # "https://giornaledibrescia.it",
    # "https://bresciaoggi.it",
    # "https://ansa.it"
]

VOCE = "it-IT-DiegoNeural"  # Oppure "it-IT-ElsaNeural" per voce femminile
VELOCITA_VOCE = "+15%"
PAUSA_TRA_NOTIZIE = (
    "300ms"  # Pausa dimezzata e serrata (puoi scendere a "200ms" o salire a"
    " "400ms")
)
FILE_OUTPUT = "notiziario.mp3"

DURATA_MASSIMA_SECONDI = 90
PAROLE_AL_SECONDO = 2.7  # Aumentato leggermente grazie alle pause più brevi


def pulisci_testo(testo):
  testo = html.unescape(testo)  # Converte eventuali simboli HTML (es. &quot;)
  testo = re.sub(r"<[^>]+>", "", testo)
  testo = re.sub(r"\s+", " ", testo).strip()
  return testo


def estrai_ultime_notizie(urls):
  articoli = []
  titoli_visti = set()

  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
          " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
      ),
      "Accept": "application/rss+xml, application/xml, text/xml, */*",
  }

  for url in urls:
    try:
      req = urllib.request.Request(url, headers=headers)
      with urllib.request.urlopen(req, timeout=15) as response:
        contenuto_xml = response.read()
      feed = feedparser.parse(contenuto_xml)
      print(f"Fonte {url} -> Trovati {len(feed.entries)} articoli")
    except Exception as e:
      print(f"Errore su {url}: {e}")
      continue

    for entry in feed.entries:
      titolo_grezzo = pulisci_testo(getattr(entry, "title", ""))
      titolo = titolo_grezzo.split(" - ")[0].strip()

      if not titolo or titolo.lower() in titoli_visti:
        continue
      titoli_visti.add(titolo.lower())

      data_pub = getattr(entry, "published_parsed", None) or getattr(
          entry, "updated_parsed", None
      )
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
    # Rimuove eventuali punti finali doppi prima di aggiungere il punto
    titolo_pulito = articolo["titolo"].rstrip(".")
    frase_notizia = f"{titolo_pulito}."
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

  # Unisce le frasi su una sola riga con una pausa breve di 300 millisecondi
  pausa_ssml = f' <break time="{PAUSA_TRA_NOTIZIE}"/> '
  testo_finale = pausa_ssml.join(copione)

  print(f"Totale notizie inserite nel GR: {notizie_raccolte}")
  print("Testo finale:\n", " ".join(copione))

  comunicazione = edge_tts.Communicate(
      testo_finale, VOCE, rate=VELOCITA_VOCE
  )
  await comunicazione.save(FILE_OUTPUT)


if __name__ == "__main__":
  asyncio.run(crea_audio())
