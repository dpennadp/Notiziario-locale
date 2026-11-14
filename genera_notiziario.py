import asyncio
import datetime
import html
import re
import urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo
import edge_tts

# --- CONFIGURAZIONE FONTI UFFICIALI ---
FEED_URLS = [
    "https://ansa.it",
    "https://ansa.it",
    "https://ansa.it",
    "https://ilpost.it",
]

VOCE = "it-IT-DiegoNeural"
VELOCITA_VOCE = "+15%"
FILE_OUTPUT = "notiziario.mp3"

DURATA_MASSIMA_SECONDI = 90
PAROLE_AL_SECONDO = 2.7


def pulisci_testo(testo):
  if not testo:
    return ""
  testo = html.unescape(testo)
  testo = re.sub(r"<[^>]+>", "", testo)
  testo = re.sub(r"\s+", " ", testo).strip()
  return testo


def estrai_ultime_notizie(urls):
  articoli = []
  titoli_visti = set()

  headers = {"User-Agent": "Mozilla/5.0 (compatible; NotiziarioBot/1.0)"}

  for url in urls:
    try:
      req = urllib.request.Request(url, headers=headers)
      with urllib.request.urlopen(req, timeout=15) as response:
        xml_data = response.read()

      root = ET.fromstring(xml_data)
      items = root.findall(".//item")
      print(f"Fonte {url} -> Trovati {len(items)} articoli")

      for item in items:
        titolo_el = item.find("title")
        if titolo_el is None or not titolo_el.text:
          continue

        titolo_grezzo = pulisci_testo(titolo_el.text)
        titolo = titolo_grezzo.strip()

        if not titolo or titolo.lower() in titoli_visti:
          continue
        titoli_visti.add(titolo.lower())

        articoli.append(titolo)

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

  ultime_notizie = estrai_ultime_notizie(FEED_URLS)

  for titolo in ultime_notizie:
    titolo_pulito = titolo.rstrip(".")
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

  testo_finale = " ".join(copione)

  print(f"Totale notizie inserite nel GR: {notizie_raccolte}")
  print("Testo finale:\n", testo_finale)

  comunicazione = edge_tts.Communicate(
      testo_finale, VOCE, rate=VELOCITA_VOCE
  )
  await comunicazione.save(FILE_OUTPUT)


if __name__ == "__main__":
  asyncio.run(crea_audio())
