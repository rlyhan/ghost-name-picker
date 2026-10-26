# ghost-name-picker

A Flask app on Google App Engine standard (Python 3.14) for picking ghost
names. It is built on [gae-secure-scaffold](https://github.com/google/gae-secure-scaffold-python3)
and stores data in Firestore in Datastore mode using `google.cloud.ndb`,
which the scaffold includes.

When setting up a new Google Cloud project, create the Firestore database in
**Datastore mode**. Firestore asks you to choose a mode when the database is
created and it can't be changed afterwards. NDB only works with Datastore
mode, so a database in the other option (Native mode) would need the app's
data code rewritten. To check an existing project:

```sh
gcloud firestore databases list  # TYPE should be DATASTORE_MODE
```

## Running locally

```sh
python3 -m venv env
source env/bin/activate

pip install -r requirements.txt
```

The app stores data in Datastore, so locally it needs the Datastore emulator
(requires Java 8+). Start it in a separate terminal and leave it running:

```sh
gcloud components install cloud-datastore-emulator  # first time only
gcloud beta emulators datastore start
```

Then, in the terminal you run the app from:

```sh
$(gcloud beta emulators datastore env-init)
export GOOGLE_CLIENT_SECRET=<client-secret>  # see "Google sign-in" below
FLASK_SETTINGS_FILENAME=settings_dev.py python main.py
```

Then open http://localhost:8080. Use `localhost` rather than the
`127.0.0.1` address the server prints, as the OAuth redirect URI is
registered for `localhost`.

## Data model

Datastore has no unique constraints, so uniqueness is enforced through keys.
Each `GhostName` is keyed by its lowercased name (e.g. `bloody mary`), which
is separate from the `name` property used for display. Renaming a ghost name
therefore means creating a new entity. Create entities through
`get_or_insert` with this key convention, not with auto-generated IDs.

## Configuration

`settings.py` holds the app's settings and is loaded in production via
`FLASK_SETTINGS_FILENAME` in `app.yaml`. Locally, `settings_dev.py` imports
it, sets `SECRET_KEY` and allows the CSRF cookie over plain HTTP; it is
excluded from deploys. In production, the scaffold generates a `SECRET_KEY` on first startup
and stores it in Datastore as an `AppConfig` entity.

### Google sign-in

Sign-in uses Google's server-side OAuth flow via Authlib, so no Google
JavaScript runs on the page and the scaffold's Content Security Policy is
unchanged. Create an OAuth client ID (type "Web application") under Google
Auth Platform → Clients, with this authorised redirect URI:

- `http://localhost:8080/auth/callback`

The client ID is set as `GOOGLE_CLIENT_ID` in `settings.py`; it is not a
secret. The client secret is read from the `GOOGLE_CLIENT_SECRET` environment
variable when the app starts, so export it in the same terminal before
starting the app. It must never be committed.

The OAuth consent screen's audience is External and in Testing, so only
accounts listed under Audience → Test users can sign in.

## Linting

```sh
pip install -r requirements-dev.txt
pylint main.py models.py import_ghost_names.py settings.py settings_dev.py
```

## Importing ghost names

`import_ghost_names.py` loads ghost names from a CSV with `Ghost name` and
`Description` columns. Each name is keyed by its lowercased value, and names
that already exist are left unchanged, so it is safe to re-run. An optional
second argument limits how many rows are imported.

```sh
python import_ghost_names.py path/to/ghost-names.csv [limit]
```

The script writes to whichever Datastore the terminal is set up for, and asks
for confirmation after showing the target project and whether it is the
emulator or production:

- **Emulator:** run `$(gcloud beta emulators datastore env-init)` first.
- **Production:** use a terminal without the emulator variables, then:

  ```sh
  gcloud auth application-default login  # first time only
  export GOOGLE_CLOUD_PROJECT=<project-id>
  python import_ghost_names.py path/to/ghost-names.csv
  ```

## Deploying

```sh
gcloud app deploy
```

The production Datastore starts empty, so run the import against production
after the first deploy.

Sign-in does not work in production yet: the client secret is only provided
locally, and the production redirect URI is not registered.
