# Risto - Strategia di Pricing e Roadmap Funzionalità

## Piani di Abbonamento

### Silver - 29 EUR/mese (249 EUR/anno)

**Target:** piccoli ristoranti, bar, trattorie, pizzerie d'asporto

| Area | Funzionalità |
|------|-------------|
| Menu digitale | Menu pubblico con categorie, piatti, ingredienti, descrizioni e prezzi |
| QR Code | Generazione QR code per ogni tavolo |
| Gestione tavoli | Fino a **15 tavoli** |
| Ordini | Ricezione ordini dal tavolo tramite QR (max **200 ordini/mese**) |
| Utenti | **1 utente** admin |
| Visibilità piatti | Mostra/nascondi piatti dal menu pubblico |
| Ordinamento | Controllo ordine di categorie e piatti |
| Supporto | Email entro 48h |

### Gold - 49 EUR/mese (419 EUR/anno)

**Target:** ristoranti strutturati, catene, locali con alto volume

| Area | Funzionalità |
|------|-------------|
| Menu digitale | Tutto Silver + **foto piatti**, **allergeni e icone dietetiche** (vegano, gluten-free, ecc.) |
| QR Code | Generazione QR code + **stampa formato A5/A6 con logo** |
| Gestione tavoli | Tavoli **illimitati** |
| Ordini | Ordini **illimitati** + **storico ordini** con filtri per data/tavolo/stato |
| Utenti | **Multi-utente** con ruoli (admin, cameriere, cucina) |
| Notifiche | **Notifiche real-time** (suono + push) per nuovi ordini |
| Comande cucina | **Vista cucina dedicata** — schermata ottimizzata per monitor/tablet in cucina |
| Report | **Dashboard analytics**: piatti più venduti, incasso giornaliero/settimanale, orari di punta |
| Multi-lingua | Menu disponibile in **2 lingue** (italiano + 1 a scelta) |
| Personalizzazione | Logo e colori personalizzati sul menu pubblico |
| Supporto | Email entro 24h + **chat WhatsApp** |

---

## Confronto rapido

| Funzionalità | Silver | Gold |
|---|:---:|:---:|
| Menu digitale | Si | Si |
| Foto piatti | - | Si |
| Allergeni e icone dietetiche | - | Si |
| QR code tavoli | Si | Si |
| QR stampabili con logo | - | Si |
| Tavoli | Max 15 | Illimitati |
| Ordini/mese | Max 200 | Illimitati |
| Storico ordini | - | Si |
| Utenti | 1 | Illimitati |
| Ruoli (cameriere, cucina) | - | Si |
| Notifiche real-time | - | Si |
| Vista cucina | - | Si |
| Analytics e report | - | Si |
| Multi-lingua | - | 2 lingue |
| Logo e colori custom | - | Si |
| Supporto | Email 48h | Email 24h + WhatsApp |

---

## Personalizzazioni a pagamento (Add-on)

Servizi acquistabili separatamente da entrambi i piani, con preventivo su richiesta o prezzo fisso.

### Hardware

| Add-on | Descrizione | Prezzo indicativo |
|--------|-------------|-------------------|
| **Tablet Cucina** | Tablet dedicato (10") pre-configurato con app vista cucina, supporto a muro incluso | 199 EUR (una tantum) |
| **Tablet Cassa** | Tablet punto cassa con app gestione ordini e chiusura giornaliera | 249 EUR (una tantum) |
| **Stampante comande** | Stampante termica per comande in cucina, integrata con il sistema ordini | 149 EUR (una tantum) |

### Funzionalità extra

| Add-on | Descrizione | Prezzo indicativo |
|--------|-------------|-------------------|
| **Pagamenti online** | Integrazione Stripe/SumUp per pagamento diretto dal tavolo | 15 EUR/mese |
| **Prenotazione tavoli** | Sistema di prenotazione online con calendario e conferma automatica | 10 EUR/mese |
| **Programma fedeltà** | Punti, premi e sconti per clienti abituali con tessera digitale | 12 EUR/mese |
| **Ordini d'asporto e delivery** | Sezione pubblica per ordini take-away con fascia oraria di ritiro | 15 EUR/mese |
| **Integrazione rider** | Collegamento con Glovo, Deliveroo, JustEat per sincronizzare il menu | 20 EUR/mese |
| **Multi-sede** | Gestione di più locali da un unico pannello admin | 19 EUR/mese per sede aggiuntiva |
| **Lingue aggiuntive** | Oltre le 2 incluse nel Gold (traduzione professionale del menu) | 39 EUR una tantum per lingua |
| **Dominio personalizzato** | Menu su dominio proprio (es. menu.mioristorante.it) con certificato SSL | 5 EUR/mese |

### Servizi professionali

| Add-on                       | Descrizione | Prezzo indicativo |
|------------------------------|-------------|-------------------|
| **Setup assistito**          | Configurazione iniziale completa: creazione menu, categorie, tavoli, QR code | 99 EUR una tantum |
| **Shooting fotografico piatti** | Servizio fotografico professionale per il menu (fino a 30 piatti) | 199 EUR una tantum |
| **Grafica menu personalizzata** | Design su misura del menu pubblico (layout, font, stile) | 149 EUR una tantum |
| **Formazione staff**         | Sessione di formazione in videochiamata per il personale (1h) | 49 EUR una tantum |
| **Sviluppo su misura**       | Funzionalità custom sviluppate ad hoc per il ristorante | A preventivo |

---

## Funzionalità da implementare - Roadmap

### Fase 1 — Fondamenta Silver (priorità alta)

- [ ] Trial gratuito 14 giorni senza carta di credito
- [ ] Sistema di registrazione e onboarding guidato
- [ ] Limiti piano Silver (max 15 tavoli, 200 ordini/mese, 1 utente)
- [ ] Pagina pricing pubblica con confronto piani
- [ ] Integrazione pagamenti abbonamento (Stripe Billing)
- [ ] Pannello gestione abbonamento (upgrade, downgrade, fatture)

### Fase 2 — Funzionalità Gold (priorità alta)

- [ ] Upload foto piatti con ridimensionamento automatico
- [ ] Gestione allergeni e icone dietetiche sui piatti
- [ ] Ruoli utente aggiuntivi: cameriere (solo ordini) e cucina (solo vista comande)
- [ ] Vista cucina dedicata (schermata fullscreen ottimizzata per tablet)
- [ ] Notifiche real-time con WebSocket (nuovo ordine, ordine pronto)
- [ ] Suono di notifica configurabile
- [ ] Storico ordini con filtri (data, tavolo, stato, importo)
- [ ] Dashboard analytics (piatti più venduti, incasso, orari di punta)
- [ ] Personalizzazione logo e colori del menu pubblico
- [ ] Supporto multi-lingua (2 lingue)
- [ ] QR code stampabili formato A5/A6 con logo del ristorante

### Fase 3 — Add-on e personalizzazioni (priorità media)

- [ ] Modulo pagamenti online (Stripe/SumUp) dal tavolo
- [ ] Sistema prenotazione tavoli con calendario
- [ ] Modulo ordini d'asporto con fascia oraria
- [ ] Supporto dominio personalizzato
- [ ] Programma fedeltà con punti e premi
- [ ] App tablet cucina (PWA ottimizzata)
- [ ] Integrazione stampante termica comande (ESC/POS)

### Fase 4 — Espansione (priorità bassa)

- [ ] Multi-sede da pannello unico
- [ ] Integrazione rider (Glovo, Deliveroo, JustEat)
- [ ] App nativa iOS/Android per il ristoratore
- [ ] API pubblica per integrazioni di terze parti
- [ ] Lingue aggiuntive con traduzione automatica assistita

---

## Note

- I prezzi degli add-on sono indicativi e da validare con analisi dei costi
- Il trial gratuito di 14 giorni è previsto per entrambi i piani
- Sconto annuale ~15-20% per incentivare abbonamenti a lungo termine
- Il tablet cucina viene venduto pre-configurato e pronto all'uso
