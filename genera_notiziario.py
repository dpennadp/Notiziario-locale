import asyncio
import datetime
import email.utils
import html
import os
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
FILE_FEED = "feed.xml"
URL_BASE = "https://github.io"

DURATA_MASSIMA_SECONDI = 90
PAROLE_AL_SECONDO = 2.7


def pulisci_testo(testo):
  if not testo:
    return ""
  testo = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", testo, flags=re.DOTALL)
  testo = html.unescape(testo)
  testo = re.sub(r"<[^>]+>", "", testo)
  testo = testo.replace("’", "'").replace("‘", "'")
  testo = testo.replace('"', "").replace("“", "").replace("”", "")
  testo = testo.replace("«", "").replace("»", "")
  testo = re.sub(r"(^|\s)'([^']+)'(\s|$|[.,;:!?])", r"\1\2\3", testo)
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
      items = re.findall(
          r"<item\b[^>]*>(.*?)</item>", risultato.stdout, flags=re.DOTALL
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

        match_desc = re.search(
            r"<description\b[^>]*>(.*?)</description>", item, flags=re.DOTALL
        )
        descrizione = ""
        if match_desc:
          descrizione = pulisci_testo(match_desc.group(1)).rstrip(".")
          if descrizione.lower().startswith(titolo.lower()):
            descrizione = descrizione[len(titolo) :].lstrip(" .:-").strip()

        titoli_visti.add(titolo.lower())

        if descrizione and len(descrizione) > 15:
          articoli.append(f"{titolo}. {descrizione}.")
        else:
          articoli.append(f"{titolo}.")

    except Exception as e:
      print(f"Errore su {url}: {e}")
      continue

  return articoli


def genera_feed_rss(adesso, ora_formattata):
  dimensione_byte = os.path.getsize(FILE_OUTPUT)
  data_rfc2822 = email.utils.format_datetime(adesso)
  id_univoco = adesso.strftime("%Y%m%d%H%M")
  url_mp3 = f"{URL_BASE}/{FILE_OUTPUT}?v={id_univoco}"

  xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://itunes.com">
  <channel>
    <title>Notiziario Locale</title>
    <link>{URL_BASE}/</link>
    <description>Edizione oraria delle notizie locali</description>
    <language>it-it</language>
    <lastBuildDate>{data_rfc2822}</lastBuildDate>
    <item>
      <title>Notiziario delle ore {ora_formattata}</title>
      <guid isPermaLink="false">notiziario-{id_univoco}</guid>
      <pubDate>{data_rfc2822}</pubDate>
      <enclosure url="{url_mp3}" length="{dimensione_byte}" type="audio/mpeg" />
    </item>
  </channel>
</rss>"""

  with open(FILE_FEED, "w", encoding="utf-8") as f:
    f.write(xml_content)
  print("Feed RSS podcast generato con successo!")


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

  for notizia in estrai_ultime_notizie(FONTI_RSS):
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

  comunicazione = edge_tts.Communicate(
      testo_finale, VOCE, rate=VELOCITA_VOCE
  )
  await comunicazione.save(FILE_OUTPUT)
  genera_feed_rss(adesso, ora_formattata)


if __name__ == "__main__":
  asyncio.run(crea_audio())
