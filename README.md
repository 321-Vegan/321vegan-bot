# Bot Discord de validation produit 321Vegan

Command
`/valider-produit ean:<EAN> resultat:<vegan|non-vegan> capture:<fichier> [raison:<choix>]`.
Bot acts like a normal contributor via the classic API endpoints.

- `POST /auth/login`
- `GET /products/ean/{ean}`
- `PUT /products/{id}`

Sync new commands with `make sync`