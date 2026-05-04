# 🚀 Deploy di Tavolò su PythonAnywhere

Guida passo-passo per pubblicare la web app **Tavolò** (Flask + SQLite) su
[PythonAnywhere](https://www.pythonanywhere.com/), anche con account **gratuito**.

> Stack: **Flask 3**, **SQLite**, upload immagini su filesystem, sessione con
> secret key. Nessun servizio esterno richiesto.

---

## 1. Prerequisiti

- Un account PythonAnywhere (anche **Free / Beginner**).
- Repository Git accessibile (es. GitHub) con il codice di Tavolò.
- Conoscere lo **username** PythonAnywhere: nei percorsi della guida sostituisci
  `<USER>` con il tuo username (es. `marione`).

> ⚠ **Limiti del piano Free**:
> - L'app dorme dopo qualche ora di inattività e va "ricaricata" (Reload) ogni
>   ~3 mesi tramite il pulsante nel pannello Web.
> - Connessioni in uscita verso Internet limitate a una whitelist (non rilevante
>   per Tavolò che non chiama servizi esterni).
> - Dominio fisso: `https://<USER>.pythonanywhere.com`.

---

## 2. Carica il codice su PythonAnywhere

Apri una **Bash console** dal pannello PythonAnywhere e clona il repo nella tua
home:

```bash
cd ~
git clone https://github.com/<tuo-utente>/tavolo_svil_free2.git tavolo
cd tavolo
```

Il percorso del progetto sarà quindi: `/home/<USER>/tavolo`.

> In alternativa puoi caricare i file via SFTP / pannello **Files**, ma `git`
> è molto più comodo per gli aggiornamenti futuri (`git pull`).

---

## 3. Crea il virtualenv e installa le dipendenze

Sempre nella Bash console:

```bash
# Verifica le versioni Python disponibili
ls /usr/bin/python3*

# Crea un virtualenv con Python 3.10 (o la più recente supportata dal tuo piano)
mkvirtualenv tavolo-venv --python=/usr/bin/python3.10

# Se il prompt non mostra (tavolo-venv), attivalo:
workon tavolo-venv

cd ~/tavolo
pip install --upgrade pip
pip install -r requirements.txt
```

`mkvirtualenv` è un helper preinstallato su PythonAnywhere che crea l'ambiente
in `~/.virtualenvs/tavolo-venv`.

---

## 4. Inizializza il database e crea l'admin

L'app crea il DB SQLite al primo avvio e chiede in console di creare l'utente
admin. Su PythonAnywhere il server web **non è interattivo**, quindi l'admin va
creato a mano dalla Bash console:

```bash
workon tavolo-venv
cd ~/tavolo
python app.py
```

Rispondi alle domande (username, password, conferma password). Quando vedi
`✅ Admin '...' creato con successo!` premi **Ctrl+C** per fermare il server di
sviluppo: in produzione lo gestirà PythonAnywhere via WSGI.

Verifica che siano stati creati:

- `~/tavolo/restaurant.db` → database SQLite
- `~/tavolo/.secret_key` → chiave di sessione (generata se manca, modalità `0600`)

---

## 5. Configura la Web App su PythonAnywhere

Dal pannello: **Web → Add a new web app**.

1. **Domain**: lascia il default `<USER>.pythonanywhere.com`.
2. **Framework**: scegli **Manual configuration** (NON il template Flask, perché
   sovrascriverebbe `app.py`).
3. **Python version**: la stessa usata per il virtualenv (es. 3.10).

Al termine vieni portato nella pagina di configurazione della web app.

### 5.1 Imposta i percorsi

Nella sezione **Code** della pagina Web:

| Campo            | Valore                                  |
| ---------------- | --------------------------------------- |
| Source code      | `/home/<USER>/tavolo`                   |
| Working directory| `/home/<USER>/tavolo`                   |
| WSGI config file | (lascia il path generato, lo modifichi sotto) |

Nella sezione **Virtualenv**:

```
/home/<USER>/.virtualenvs/tavolo-venv
```

### 5.2 Modifica il file WSGI

Clicca sul link del **WSGI configuration file**
(es. `/var/www/<USER>_pythonanywhere_com_wsgi.py`).

Sostituisci tutto il contenuto con:

```python
import os
import sys

# Percorso del progetto
project_home = "/home/<USER>/tavolo"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# (Opzionale ma consigliato) variabili d'ambiente
# Genera una chiave forte una sola volta, p.es. con:
#   python -c "import secrets; print(secrets.token_hex(32))"
os.environ["FLASK_SECRET_KEY"] = "incolla-qui-una-chiave-lunga-e-casuale"

# Importa l'app Flask
from app import app as application  # noqa: E402
```

> 🔐 Impostando `FLASK_SECRET_KEY` come variabile d'ambiente non è più
> necessario il file `.secret_key` su disco. Cambiando la chiave, **tutte le
> sessioni esistenti vengono invalidate** (gli admin dovranno rifare login).

### 5.3 Static files (importante per immagini, CSS, QR)

Nella sezione **Static files** della pagina Web aggiungi una mappatura:

| URL       | Directory                                |
| --------- | ---------------------------------------- |
| `/static/`| `/home/<USER>/tavolo/static/`            |

Così PythonAnywhere serve direttamente i file statici (incluso
`static/uploads/dishes/` con le foto dei piatti) senza passare da Flask.

### 5.4 Reload

Premi il pulsante verde **Reload <USER>.pythonanywhere.com** in alto.
Apri `https://<USER>.pythonanywhere.com/` → dovresti vedere il menu pubblico.
Login admin su `https://<USER>.pythonanywhere.com/login`.

---

## 6. Permessi cartelle scrivibili

L'app scrive in:

- `restaurant.db` (e file ausiliari `-journal`, `-wal`, `-shm`)
- `static/uploads/dishes/` (immagini caricate dagli utenti)
- `archives/` (export degli ordini archiviati)
- `.secret_key` (solo se **non** usi `FLASK_SECRET_KEY` via env)

Assicurati che esistano e siano scrivibili dall'utente:

```bash
cd ~/tavolo
mkdir -p static/uploads/dishes archives
chmod 700 archives
```

> Su PythonAnywhere giri sempre come il tuo utente, quindi non servono
> permessi speciali — basta che le cartelle esistano.

---

## 7. Log e debug

Dalla pagina Web del pannello hai tre link utili in alto:

- **Access log** — richieste HTTP.
- **Error log** — eccezioni Python e traceback (è il primo da guardare se la
  pagina dà *Something went wrong*).
- **Server log** — output del processo WSGI.

Per un debug rapido locale puoi anche fare nella Bash console:

```bash
workon tavolo-venv
cd ~/tavolo
FLASK_DEBUG=1 python app.py
```

> ⚠ **Mai** lasciare `FLASK_DEBUG=1` sul WSGI di produzione: espone una console
> Python remota con esecuzione arbitraria di codice.

---

## 8. Aggiornare l'app dopo modifiche

Workflow tipico per pubblicare nuove versioni:

```bash
workon tavolo-venv
cd ~/tavolo
git pull
pip install -r requirements.txt   # se sono cambiate dipendenze
```

Poi premi **Reload** nella pagina Web del pannello PythonAnywhere.

> Il `restaurant.db` è ignorato da git (`.gitignore`), quindi i dati di
> produzione **non** vengono sovrascritti dai `git pull`.

---

## 9. Backup del database

SQLite è un singolo file: bastano copie periodiche di `restaurant.db`.

Backup manuale dalla Bash console:

```bash
cd ~/tavolo
cp restaurant.db "backups/restaurant-$(date +%Y%m%d-%H%M).db"
```

Per un backup automatico puoi usare i **Scheduled tasks** di PythonAnywhere
(disponibili anche sul piano Free, una task al giorno):

1. **Tasks → Schedule a new task**
2. Comando:
   ```bash
   /bin/bash -lc 'mkdir -p /home/<USER>/tavolo/backups && cp /home/<USER>/tavolo/restaurant.db /home/<USER>/tavolo/backups/restaurant-$(date +\%Y\%m\%d).db'
   ```
3. Imposta orario (UTC).

Per portare il backup in locale: pannello **Files** → naviga in `backups/` →
**Download**.

---

## 10. (Opzionale) Dominio personalizzato

Disponibile solo sui piani **a pagamento**. In sintesi:

1. Pannello **Web** → **Add a new web app** → inserisci il tuo dominio
   (`menu.miristorante.it`).
2. Configura nel tuo DNS un record **CNAME** verso
   `<USER>.pythonanywhere.com`.
3. Abilita HTTPS gratuito tramite Let's Encrypt dalla pagina Web.

---

## 11. Checklist finale

- [ ] Repo clonato in `/home/<USER>/tavolo`
- [ ] Virtualenv `tavolo-venv` creato e dipendenze installate
- [ ] Admin creato lanciando `python app.py` una volta in console
- [ ] WSGI configurato con `from app import app as application`
- [ ] `FLASK_SECRET_KEY` impostata nel file WSGI
- [ ] Mapping static `/static/ → /home/<USER>/tavolo/static/`
- [ ] Cartelle `static/uploads/dishes/` e `archives/` esistenti e scrivibili
- [ ] **Reload** della web app
- [ ] Menu pubblico raggiungibile su `https://<USER>.pythonanywhere.com/`
- [ ] Login admin funzionante su `/login`
- [ ] Task schedulata di backup (opzionale)

Buon deploy! 🍽
