from google.cloud import ndb

class GhostName(ndb.Model):
    name = ndb.StringProperty(required=True)
    description = ndb.TextProperty()
