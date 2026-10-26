"""Flask app that lists ghost names stored in Datastore."""

import random

import flask
import securescaffold
from authlib.integrations import base_client
from authlib.integrations import flask_client
from google.cloud import ndb
from werkzeug.middleware import proxy_fix

import models

app = securescaffold.create_app(__name__)
ndb_client = ndb.Client()
oauth = flask_client.OAuth(app)

# Google's OpenID metadata: its auth, token and signing-key endpoints.
CONF_URL = "https://accounts.google.com/.well-known/openid-configuration"
google = oauth.register(
    name="google",
    server_metadata_url=CONF_URL,
    # Client ID and secret from the Google Auth Platform client, via settings.
    client_id=app.config["GOOGLE_CLIENT_ID"],
    client_secret=app.config["GOOGLE_CLIENT_SECRET"],
    client_kwargs={"scope": "openid email profile"},
)


def ndb_wsgi_middleware(wsgi_app):
    """Wraps a WSGI app so every request runs inside an NDB context."""
    def middleware(environ, start_response):
        with ndb_client.context():
            return wsgi_app(environ, start_response)

    return middleware


app.wsgi_app = ndb_wsgi_middleware(app.wsgi_app)
# App Engine terminates HTTPS at its front end and sets X-Forwarded-Proto;
# trusting it makes url_for(_external=True) build https:// callback URLs.
app.wsgi_app = proxy_fix.ProxyFix(app.wsgi_app, x_proto=1)


@app.route("/")
def root():
    """Renders the homepage with all ghost names and their assigned users."""
    ghost_names = models.GhostName.query().order(models.GhostName.name).fetch()
    user_keys = [ghost.user_id for ghost in ghost_names if ghost.user_id]
    users = {user.key: user for user in ndb.get_multi(user_keys) if user}
    current_user = signed_in_user()
    current_ghost = current_user and next(
        (g for g in ghost_names if g.key == current_user.ghost_name), None
    )
    return flask.render_template(
        "index.html",
        ghost_names=ghost_names,
        users=users,
        email=flask.session.get("email"),
        current_user=current_user,
        current_ghost=current_ghost,
    )


@app.route("/login")
def login():
    """Redirects the user to Google to sign in."""
    redirect_uri = flask.url_for("auth_callback", _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route("/auth/callback")
def auth_callback():
    """Completes Google sign-in and stores the verified user in the session."""
    try:
        token = google.authorize_access_token()
    except base_client.OAuthError as error:
        app.logger.warning("Google sign-in failed: %s", error)
        flask.abort(401)

    userinfo = token["userinfo"]
    if not userinfo.get("email_verified"):
        flask.abort(401)

    models.User.get_or_insert(
        userinfo["sub"],
        google_auth_id=userinfo["sub"],
        email_address=userinfo["email"],
    )

    flask.session["google_auth_id"] = userinfo["sub"]
    flask.session["email"] = userinfo["email"]
    return flask.redirect(flask.url_for("root"))


MAX_NAME_LENGTH = 100


def signed_in_user():
    """Returns the signed-in User, or None if nobody is signed in."""
    google_auth_id = flask.session.get("google_auth_id")
    return google_auth_id and models.User.get_by_id(google_auth_id)


@app.route("/enter-name", methods=["GET", "POST"])
def enter_name():
    """Shows and saves the signed-in user's first and last name."""
    user = signed_in_user()
    if not user:
        return flask.redirect(flask.url_for("login"))

    if flask.request.method == "GET":
        return flask.render_template(
            "enter_name.html",
            first_name=user.first_name or "",
            last_name=user.last_name or "",
        )

    first_name = flask.request.form.get("first_name", "").strip()
    last_name = flask.request.form.get("last_name", "").strip()
    if not first_name or not last_name:
        return flask.render_template(
            "enter_name.html",
            first_name=first_name,
            last_name=last_name,
            error="Please enter both your first name and last name.",
        ), 400
    if max(len(first_name), len(last_name)) > MAX_NAME_LENGTH:
        return flask.render_template(
            "enter_name.html",
            first_name=first_name[:MAX_NAME_LENGTH],
            last_name=last_name[:MAX_NAME_LENGTH],
            error=f"Names must be at most {MAX_NAME_LENGTH} characters.",
        ), 400

    save_name(user.key, first_name, last_name)
    return flask.redirect(flask.url_for("ghost_name_results"), 303)


@ndb.transactional()
def save_name(user_key, first_name, last_name):
    """Saves the user's name without overwriting a concurrent ghost name."""
    user = user_key.get()
    user.first_name = first_name
    user.last_name = last_name
    user.put()


@ndb.transactional()
def choose_ghost_name(user_key, ghost_key):
    """Assigns ghost_key to the user, releasing their previous ghost name.

    The user, the chosen ghost name and the previous one are all read by key
    inside the transaction, so a ghost name can never be assigned to two users,
    nor a user hold two ghost names.

    Args:
        user_key: Key of the user choosing a ghost name.
        ghost_key: Key of the chosen ghost name.

    Returns:
        False if the ghost name no longer exists or belongs to another user.
    """
    user, ghost = ndb.get_multi([user_key, ghost_key])
    if not ghost or (ghost.user_id and ghost.user_id != user_key):
        return False

    entities = [user, ghost]
    if user.ghost_name and user.ghost_name != ghost_key:
        previous = user.ghost_name.get()
        if previous and previous.user_id == user_key:
            previous.user_id = None
            entities.append(previous)

    ghost.user_id = user_key
    user.ghost_name = ghost_key
    ndb.put_multi(entities)
    return True


def render_results(user, error=None, status=200):
    """Renders up to 3 random available ghost names and remembers the offer."""
    available = [
        ghost
        for ghost in models.GhostName.query().fetch()
        if not ghost.user_id
    ]
    options = random.sample(available, min(3, len(available)))
    flask.session["offered_ghost_names"] = [ghost.key.id() for ghost in options]
    return flask.render_template(
        "ghost_name_results.html",
        options=[
            (ghost.key.id(), f"{user.first_name} {ghost.name} {user.last_name}")
            for ghost in options
        ],
        error=error,
    ), status


@app.route("/ghost-name-results", methods=["GET", "POST"])
def ghost_name_results():
    """Offers up to 3 ghost names and assigns the one the user picks."""
    user = signed_in_user()
    if not user:
        return flask.redirect(flask.url_for("login"))
    if not user.first_name or not user.last_name:
        return flask.redirect(flask.url_for("enter_name"))

    if flask.request.method == "GET":
        return render_results(user)

    choice = flask.request.form.get("ghost_name")
    if choice not in flask.session.get("offered_ghost_names", []):
        return render_results(
            user,
            error="Please choose one of the ghost names shown.",
            status=400,
        )

    if not choose_ghost_name(user.key, ndb.Key(models.GhostName, choice)):
        return render_results(
            user,
            error="Sorry, that ghost name was just taken. Please choose again.",
            status=409,
        )

    flask.session.pop("offered_ghost_names", None)
    return flask.redirect(flask.url_for("root"), 303)


@app.route("/logout", methods=["POST"])
def logout():
    """Signs the user out."""
    flask.session.clear()
    return flask.redirect(flask.url_for("root"), 303)


if __name__ == "__main__":
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    # Flask's development server will automatically serve static files in
    # the "static" directory. See:
    # http://flask.pocoo.org/docs/1.0/quickstart/#static-files. Once deployed,
    # App Engine itself will serve those files as configured in app.yaml.
    app.run(host="127.0.0.1", port=8080, debug=True)
