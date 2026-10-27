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

Each `User` is keyed by their Google account ID (the ID token's `sub` claim),
which never changes, unlike the account's email address. Signing in calls
`User.get_or_insert`, so a user is created on their first sign-in and reused
afterwards. `first_name` and `last_name` are left empty at sign-in and are
entered by the user on `/enter-name`. Existing users are not updated on later
sign-ins.

After entering their name, the user is redirected to `/ghost-name-results`,
which shows up to 3 randomly chosen unassigned ghost names, each formatted as
first name, ghost name, last name (e.g. "Ada Casper Lovelace"). The offered
ghost names are remembered in the session, and the user picks one and submits.
Only an offered ghost name is accepted (400 otherwise); if it was taken in the
meantime the page shows fresh options (409). On success the user is
redirected to the overview, which lists every ghost name with the name and
email of the user who took it, and shows the signed-in user's current ghost
name. Choosing again releases the user's previous ghost name.

The assignment is stored on both sides, as `GhostName.user_id` and
`User.ghost_name`, so it can be checked and changed in a single transaction
that reads every entity involved by key: a ghost name is never given to two
users, and a user never holds two ghost names. (Queries can't be used for
this check, because Datastore only allows ancestor queries inside
transactions.)

## Configuration

`settings.py` holds the app's settings and is loaded in production via
`FLASK_SETTINGS_FILENAME` in `app.yaml`. Locally, `settings_dev.py` imports
it, sets `SECRET_KEY` and allows the CSRF cookie over plain HTTP; it is
excluded from deploys. In production, the scaffold generates a `SECRET_KEY` on first startup
and stores it in Datastore as an `AppConfig` entity.

### Google sign-in

Sign-in uses Google's server-side OAuth flow via Authlib, so no Google
JavaScript runs on the page and the scaffold's Content Security Policy is
unchanged. Visiting `/login` while already signed in redirects to the
overview, so a session can't be silently switched to another Google account;
to switch accounts, sign out first. Create an OAuth client ID (type "Web application") under Google
Auth Platform → Clients, with these authorised redirect URIs:

- `http://localhost:8080/auth/callback`
- `https://<default-hostname>/auth/callback`, where the hostname comes from
  `gcloud app describe --format="value(defaultHostname)"`

The client ID is set as `GOOGLE_CLIENT_ID` in `settings.py`; it is not a
secret. The client secret must never be committed:

- **Locally**, it is read from the `GOOGLE_CLIENT_SECRET` environment variable
  when the app starts, so export it in the same terminal before starting the
  app.
- **In production**, it is read from the Secret Manager secret
  `google-client-secret`, which the App Engine service account needs
  permission to access (see "Deploying").

The OAuth consent screen's audience is External and in Testing, so only
accounts listed under Audience → Test users can sign in.

## Linting

```sh
pip install -r requirements-dev.txt
pylint main.py models.py import_ghost_names.py settings.py settings_dev.py tests
```

## Testing

```sh
pip install -r requirements-dev.txt
pytest
```

The tests start their own in-memory Datastore emulator on a free port with a
temporary data directory, so they don't need (or touch) the development
emulator. Java and the emulator component must be installed (see "Running
locally").

`tests/routes/` checks the status code of every route, with one file per
route group:

- `test_overview.py`: the overview is public and returns `200`.
- `test_auth.py`: `/login` redirects to Google when signed out and to the
  overview when signed in; `/auth/callback` returns `401` for a forged
  `state` or unverified email without signing anyone in, and sets a
  `Secure`, `HttpOnly` session cookie on success; `/logout` needs a
  CSRF token (`403`) and signs the user out (`303`). Google sign-in is
  stubbed, so no OAuth secret or network sign-in is needed.
- `test_enter_name.py`: `/enter-name` redirects to sign-in when signed out;
  without a CSRF token (`403`), with an empty name (`400`) or with a name over
  100 characters (`400`) nothing is saved; a valid name is saved (trimmed)
  and redirects to the results page (`303`).
- `test_ghost_name_results.py`: `/ghost-name-results` redirects to sign-in
  when signed out and to `/enter-name` without a name; submitting nothing or
  a ghost name that wasn't shown to the user returns `400`, and one already
  taken by another user returns `409`, without assigning anything; a valid
  choice is assigned on both sides and redirects to the overview (`303`).

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

Before the first deploy, store the OAuth client secret in Secret Manager and
let the App Engine service account read it:

```sh
gcloud services enable secretmanager.googleapis.com
printf '%s' "$GOOGLE_CLIENT_SECRET" | \
  gcloud secrets create google-client-secret --data-file=-
gcloud secrets add-iam-policy-binding google-client-secret \
  --member="serviceAccount:<project-id>@appspot.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

Then deploy:

```sh
gcloud app deploy
```

The production Datastore starts empty, so run the import against production
after the first deploy.

To rotate the client secret, add a new version with
`gcloud secrets versions add google-client-secret --data-file=-` and redeploy
(or wait for new instances); the app reads the latest version on startup.
