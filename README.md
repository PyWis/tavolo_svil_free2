# 🍽 Tavolò

Web app Flask per la gestione del menu di un ristorante con pannello di amministrazione.

## Funzionalità

- **Menu pubblico** — Pagina pubblica con il menu organizzato per categorie
- **Autenticazione** — Login con username e password
- **Ruoli utente** — Admin (crea/gestisce utenti) e User (gestisce menu)
- **CRUD Categorie** — Crea, modifica, elimina categorie del menu
- **CRUD Piatti** — Ogni piatto ha: Titolo, Ingredienti, Descrizione, Prezzo
- **Visibilità** — Nascondi/mostra piatti dal menu pubblico
- **Ordinamento** — Controlla l'ordine di categorie e piatti
- **Setup CLI** — Al primo avvio crea l'utente admin da terminale

## Requisiti

- Python 3.8+
- Flask (`pip install flask`)

## Avvio

```bash
cd restaurant_app
pip install flask
python app.py
```

Al **primo avvio** verrà chiesto di creare l'utente amministratore dal terminale:

```
=============================================
  🍽  TAVOLÒ — Primo Avvio
=============================================

  Nessun amministratore trovato.
  Crea il primo utente admin per iniziare.

  👤 Username admin: admin
  🔑 Password admin: ****
  🔑 Conferma password: ****

  ✅ Admin 'admin' creato con successo!
=============================================
```

Poi il server sarà disponibile su:

- **Menu pubblico**: http://127.0.0.1:5000/
- **Login admin**: http://127.0.0.1:5000/login

## Struttura

```
restaurant_app/
├── app.py              # Applicazione Flask principale
├── restaurant.db       # Database SQLite (creato automaticamente)
├── README.md
└── templates/
    ├── base.html           # Layout base (navbar, stili)
    ├── public_menu.html    # Menu pubblico
    ├── login.html          # Pagina di login
    ├── dashboard.html      # Dashboard admin
    ├── users.html          # Lista utenti (solo admin)
    ├── user_form.html      # Crea utente (solo admin)
    ├── categories.html     # Lista categorie
    ├── category_form.html  # Crea/modifica categoria
    ├── menu_list.html      # Lista piatti
    └── menu_form.html      # Crea/modifica piatto
```

## Colori

Il tema usa una palette **Rosso e Bianco**:
- Rosso primario: `#B71C1C`
- Rosso scuro: `#7F0000`
- Bianco caldo: `#FFF8F0`
