# ghost-name-picker

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
FLASK_SETTINGS_FILENAME=settings_dev.py python main.py
```

Then open http://localhost:8080
