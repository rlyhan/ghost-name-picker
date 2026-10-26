"""Datastore models for the ghost name picker."""

from google.cloud import ndb


class GhostName(ndb.Model):
    """A ghost name, keyed by its lowercased name to keep names unique."""

    name = ndb.StringProperty(required=True)
    description = ndb.TextProperty()
