# Bot Discord de validation produit 321Vegan

Command
`/valider-produit ean:<EAN> resultat:<vegan|non-vegan> capture:<fichier> [raison:<choix>]`.
The bot uses a dedicated API account with the `admin` role so it can resolve a
Checking created by another contributor through the classic API endpoints.

- `POST /auth/login`
- `GET /products/ean/{ean}`
- `PUT /checkings/{id}`
- `PUT /products/{id}`

Sync new commands with `make sync`
