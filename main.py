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
    """Renders the homepage with all ghost names, sorted by name."""
    ghost_names = models.GhostName.query().order(models.GhostName.name).fetch()
    return flask.render_template(
        "index.html",
        ghost_names=ghost_names,
        email=flask.session.get("email"),
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

    user.first_name = first_name
    user.last_name = last_name
    user.put()
    return flask.redirect(flask.url_for("ghost_name_results"), 303)


@app.route("/ghost-name-results")
def ghost_name_results():
    """Shows up to 3 available ghost names, formatted with the user's name."""
    user = signed_in_user()
    if not user:
        return flask.redirect(flask.url_for("login"))
    if not user.first_name or not user.last_name:
        return flask.redirect(flask.url_for("enter_name"))

    available = [
        ghost
        for ghost in models.GhostName.query().fetch()
        if not ghost.user_id
    ]
    options = random.sample(available, min(3, len(available)))
    return flask.render_template(
        "ghost_name_results.html",
        options=[
            f"{user.first_name} {ghost.name} {user.last_name}"
            for ghost in options
        ],
    )


@app.route("/logout", methods=["POST"])
def logout():
    """Signs the user out."""
    flask.session.clear()
    return flask.redirect(flask.url_for("root"))


if __name__ == "__main__":
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    # Flask's development server will automatically serve static files in
    # the "static" directory. See:
    # http://flask.pocoo.org/docs/1.0/quickstart/#static-files. Once deployed,
    # App Engine itself will serve those files as configured in app.yaml.
    app.run(host="127.0.0.1", port=8080, debug=True)
