# Finguard API

Base URL:

```text
https://finguard-81qn.onrender.com
```

Swagger UI:

```text
https://finguard-81qn.onrender.com/docs
```

## Passwords

Every request must include the password in this header:

```http
X-API-Password: YOUR_PASSWORD
```

Government endpoints use the value configured as:

```env
GOVT_API_PASSWORD=your-government-password
```

Finguard endpoints use the value configured as:

```env
FINGUARD_API_PASSWORD=your-finguard-password
```

## Government endpoints

### POST `/govt/documents`

Uploads an original document.

Headers:

```http
X-API-Password: GOVERNMENT_PASSWORD
Content-Type: application/json
```

Request body:

```json
{
  "reference_no": "20261234",
  "doc_name": "Test_file",
  "base64": "SGVsbG8sIFdvcmxkIQ=="
}
```

Response (`201 Created`):

```json
{
  "doc_id": "b99ccf84-21dd-4e4c-90de-e11c4f915a1f"
}
```

### GET `/govt/documents`

Returns all uploaded document IDs.

Headers:

```http
X-API-Password: GOVERNMENT_PASSWORD
```

Request body: none.

Response (`200 OK`):

```json
[
  "70719f8b-1d36-4b03-8b6a-1acccc665432",
  "b99ccf84-21dd-4e4c-90de-e11c4f915a1f"
]
```

### GET `/govt/documents/{document_id}/analyzed`

Returns the analyzed version of a document as Base64.

Headers:

```http
X-API-Password: GOVERNMENT_PASSWORD
```

Request body: none.

Response (`200 OK`, `text/plain`):

```text
UFJFUFJPQ0VTU0VEX0RPQ1VNRU5U
```

Returns `404` if the analyzed document has not been uploaded yet.

## Finguard endpoints

### GET `/finguard/documents/pending`

Returns document IDs that have not been analyzed yet.

Headers:

```http
X-API-Password: FINGUARD_PASSWORD
```

Request body: none.

Response (`200 OK`):

```json
[
  "b99ccf84-21dd-4e4c-90de-e11c4f915a1f"
]
```

### GET `/finguard/documents/{document_id}/raw`

Returns the original document metadata and Base64 content.

Headers:

```http
X-API-Password: FINGUARD_PASSWORD
```

Request body: none.

Response (`200 OK`):

```json
{
  "reference_no": "20261234",
  "doc_name": "Test_file",
  "base64": "SGVsbG8sIFdvcmxkIQ=="
}
```

Older documents without metadata return empty strings for `reference_no` and `doc_name`.

### POST `/finguard/documents/{document_id}/analyzed`

Uploads the analyzed version using the same document ID.

Headers:

```http
X-API-Password: FINGUARD_PASSWORD
Content-Type: text/plain
```

Request body:

```text
UFJFUFJPQ0VTU0VEX0RPQ1VNRU5U
```

Response (`201 Created`):

```json
{
  "document_id": "b99ccf84-21dd-4e4c-90de-e11c4f915a1f"
}
```

Returns `404` if the original document ID does not exist and `409` if an analyzed version already exists.
