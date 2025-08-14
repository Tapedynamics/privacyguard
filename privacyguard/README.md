# PrivacyGuard

PrivacyGuard è una applicazione web self‑hosted pensata per aiutare i fotografi professionisti a gestire il consenso alla pubblicazione delle fotografie. Consente di caricare immagini, rilevare automaticamente i volti, associare nomi e gestire lo stato del consenso, esportare le foto approvate e generare versioni con volti sfocati quando necessario. I visitatori delle escursioni possono caricare un selfie e scaricare in dimensione originale le foto in cui compaiono.

## Funzionalità principali

* **Upload asincrono**: l’upload di centinaia di foto al giorno viene gestito in background tramite una coda (RabbitMQ) e worker Celery. L’utente carica le immagini senza attendere la conclusione del riconoscimento facciale.
* **Riconoscimento facciale**: l’API Amazon Rekognition viene utilizzata per rilevare volti nelle immagini e per indicizzare volti nominati. Quando un cliente carica un selfie, la funzionalità di ricerca restituisce tutte le foto in cui appare quella persona.
* **Gestione consensi**: per ogni volto rilevato l’amministratore può assegnare un nome e definire lo stato del consenso (pending/approved/rejected). Le foto con tutti i volti approvati possono essere esportate così come sono, mentre per le altre è possibile generare una versione sfocata.
* **Esportazione**: download di un archivio `.zip` con tutte le foto approvate oppure con le versioni sfocate delle foto non approvate.
* **Front‑end reattivo**: interfaccia sviluppata con React e Material UI, con login, dashboard, vista di dettaglio della foto (con overlay dei riquadri faccia), upload multiplo e ricerca cliente.

## Struttura del repository

```
privacyguard/
├── backend/           # codice del backend FastAPI
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py         # definizione delle API
│       ├── models.py       # ORM SQLAlchemy
│       ├── schemas.py      # Pydantic
│       ├── auth.py         # autenticazione JWT
│       ├── database.py     # configurazione DB
│       └── celery_app.py   # configurazione Celery
├── worker/            # worker Celery per elaborazioni asincrone
│   ├── Dockerfile
│   └── tasks.py
├── frontend/          # applicazione React/Vite
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx
│       └── pages/
├── docker-compose.yml # orchestrazione servizi
└── README.md          # questo file
```

## Requisiti

* **Docker e Docker Compose**: l’intera applicazione può essere avviata con un solo comando grazie a `docker-compose`. Non è necessario installare Python, Node o altri ambienti sul sistema host.
* **Chiavi AWS per Rekognition**: per utilizzare Amazon Rekognition sono necessari access key ID e secret key di un account AWS abilitato al servizio. Se non si desidera utilizzare Rekognition è possibile disabilitare le funzionalità di ricerca caricando comunque le foto (vedi sezione "Configurazione").

## Configurazione e avvio

1. **Clonare il repository** e posizionarsi nella cartella `privacyguard`.
2. **Preparare le variabili d’ambiente** (facoltativo):

   Le variabili seguenti hanno valori di default definiti in `docker-compose.yml` e nel codice. Per un’installazione su AWS o un ambiente diverso da MinIO occorre personalizzarle:

   | Variabile                       | Descrizione                                                                    |
   |--------------------------------|--------------------------------------------------------------------------------|
   | `POSTGRES_USER`/`POSTGRES_PASSWORD` | credenziali per PostgreSQL                                                   |
   | `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` | credenziali per S3/MinIO e Rekognition                               |
   | `AWS_ENDPOINT_URL`              | endpoint per S3 (es. `http://minio:9000` per MinIO; omettere per AWS S3)      |
   | `AWS_USE_SSL`                   | `true` se si usa HTTPS con S3/MinIO                                            |
   | `AWS_REGION`                    | regione AWS per Rekognition                                                    |
   | `S3_BUCKET`                     | nome del bucket dove salvare le foto                                          |
   | `AWS_REKOGNITION_COLLECTION`    | nome della collection Rekognition per indicizzare volti                      |
   | `DEFAULT_ADMIN_PASSWORD`        | password iniziale dell’utente admin                                           |

   È possibile modificare questi valori direttamente nel file `docker-compose.yml` o impostarli come variabili d’ambiente nel sistema host.

   Per facilitare la configurazione è fornito un file di esempio `.env.example`. Copiare questo file in `.env` e impostare le proprie credenziali:

   ```sh
   cp .env.example .env
   # modificare .env con le proprie chiavi
   ```

   In particolare, per il servizio di riconoscimento facciale AWS Rekognition è necessario fornire `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` e `AWS_REGION` di un account AWS abilitato. Se si utilizza MinIO in locale, questi parametri vengono usati solo per lo storage.

3. **Avvio con Docker Compose**:

   ```sh
   docker-compose up --build
   ```

   Questo comando costruirà le immagini di backend, worker e frontend, avvierà PostgreSQL, RabbitMQ, MinIO e i vari servizi. L’API sarà disponibile su `http://localhost:8000`, l’interfaccia React su `http://localhost:3000`.

4. **Accesso all’interfaccia**:

   * Aprire `http://localhost:3000` nel browser.
   * Effettuare il login con utente `admin` e la password definita in `DEFAULT_ADMIN_PASSWORD` (valore predefinito `admin`).
   * Caricare foto tramite la sezione **Upload**, attendere che la colonna "Faces" della Dashboard mostri quanti volti sono stati rilevati.
   * Cliccare su **Details** per visualizzare l’immagine con i riquadri dei volti; da qui è possibile assegnare un nome ai volti, modificare il consenso e generare una versione sfocata.
   * La sezione **Client Search** permette ai clienti di caricare un selfie e ottenere i link alle foto in cui appaiono (dimensione originale, non compresso).

## Note sull’integrazione Amazon Rekognition

* **Creazione della collection**: la collection Rekognition indicata dalla variabile `AWS_REKOGNITION_COLLECTION` viene creata automaticamente al primo utilizzo. Ogni volta che si assegna un nome a un volto viene eseguito un task Celery che ritaglia il volto e lo indicizza nella collection.
* **Costi**: Amazon Rekognition applica tariffe diverse per il rilevamento (`DetectFaces`) e l’indicizzazione/ricerca (`IndexFaces`, `SearchFacesByImage`). Consultare la documentazione AWS per maggiori dettagli.
* **MinIO come storage S3**: in ambiente locale l’applicazione utilizza MinIO come storage compatibile S3. Per passare a un bucket AWS S3 è sufficiente eliminare `AWS_ENDPOINT_URL`, impostare `AWS_USE_SSL=true` e fornire le credenziali AWS appropriate.

## Limitazioni e miglioramenti futuri

* L’interfaccia admin è minimale e può essere estesa con filtri per stato, ricerca, paginazione e visualizzazioni più avanzate.
* Non sono presenti test automatici; l’aggiunta di unit test e test end‑to‑end migliorerebbe l’affidabilità.
* Attualmente il file ZIP di esportazione delle versioni sfocate viene generato al volo; per volumi molto grandi potrebbe essere opportuno creare le versioni sfocate in anticipo tramite task Celery e memorizzarle in S3.

## Credits

Progetto sviluppato come esercitazione dall’agente AI per soddisfare i requisiti di gestione della privacy nelle fotografie di eventi.