import securescaffold
from flask import render_template
from google.cloud import ndb

from models import GhostName

app = securescaffold.create_app(__name__)
ndb_client = ndb.Client()


def ndb_wsgi_middleware(wsgi_app):
    def middleware(environ, start_response):
        with ndb_client.context():
            return wsgi_app(environ, start_response)

    return middleware


app.wsgi_app = ndb_wsgi_middleware(app.wsgi_app)


@app.route("/")
def root():
    ghost_names = GhostName.query().order(GhostName.name).fetch()
    return render_template("index.html", ghost_names=ghost_names)


if __name__ == "__main__":
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    # Flask's development server will automatically serve static files in
    # the "static" directory. See:
    # http://flask.pocoo.org/docs/1.0/quickstart/#static-files. Once deployed,
    # App Engine itself will serve those files as configured in app.yaml.
    app.run(host="127.0.0.1", port=8080, debug=True)