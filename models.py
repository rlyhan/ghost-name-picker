"""Datastore models for the ghost name picker."""

from google.cloud import ndb


class User(ndb.Model):
    """A signed-in user, keyed by their Google account ID to keep it unique."""

    google_auth_id = ndb.StringProperty(required=True)
    email_address = ndb.StringProperty(required=True)
    first_name = ndb.StringProperty()
    last_name = ndb.StringProperty()


class GhostName(ndb.Model):
    """A ghost name, keyed by its lowercased name to keep names unique."""

    name = ndb.StringProperty(required=True)
    description = ndb.TextProperty()
    user_id = ndb.KeyProperty(kind=User)
