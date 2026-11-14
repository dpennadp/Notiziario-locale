import asyncio
import datetime
import html
import re
import subprocess
from zoneinfo import ZoneInfo
import edge_tts

# --- CONFIGURAZIONE RICERCHE NOTIZIE LOCALI ---
# Puoi cambiare "Piacenza" con "Brescia" o qualsiasi altra città
RICERCHE_GOOGLE_NEWS = [
    "https://google.com",
    "https://google.com",
    "https://google.com",
]

VOCE = "it-IT-DiegoNeural"
VELOCITA_VOCE = "+15%"
FILE_OUTPUT = "notiziario.mp3"

DURATA_MASSIMA_SECONDI = 90
PAROLE_AL_SECONDO = 2.7


def pulisci_testo(testo):
  if not testo:
    return ""
  testo = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", testo, flags=re.DOTALL)
  testo = html.unescape(testo)
  testo = re.sub(r"<[^>]+>", "", testo)
  testo = re.sub(r"\s+", " ", testo).strip()
  return testo


def estrai_ultime_notizie(urls):
  articoli = []
  titoli_visti = set()

  for url in urls:
    try:
      # Usa curl nativo di Ubuntu per scaricare i feed senza blocchi DNS o SSL
      risultato = subprocess.run(
          ["curl", "-s", "-L", "-A", "Mozilla/5.0", url],
          capture_output=True,
          text=True,
          timeout=15,
      )
      testo_grezzo = risultato.stdout

      items = re.findall(
          r"<item\b[^>]*>(.*?)</item>", testo_grezzo, flags=re.DOTALL
      )
      print(f"Fonte {url[:45]}... -> Trovati {len(items)} articoli")

      for item in items[:5]:
        match_titolo = re.search(
            r"<title\b[^>]*>(.*?)</title>", item, flags=re.DOTALL
        )
        if not match_titolo:
          continue

        titolo_grezzo = pulisci_testo(match_titolo.group(1))
        # Rimuove il nome del giornale in fondo al titolo (es. " - Libertà")
        titolo = re.sub(r"\s+-\s+[^-]+$", "", titolo_grezzo).strip()

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

  ultime_notizie = estrai_ultime_notizie(RICERCHE_GOOGLE_NEWS)

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
