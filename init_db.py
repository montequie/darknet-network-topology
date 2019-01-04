import pyorient

def initGraphDB(db_name):
    # create a database
    orientdb_client.db_create(F"{db_name}",pyorient.DB_TYPE_GRAPH, pyorient.STORAGE_TYPE_PLOCAL)
    #orientdb_client.db_create(F"{db_name}", pyorient.DB_TYPE_GRAPH, pyorient.STORAGE_TYPE_MEMORY)
    orientdb_client.db_open(F"{db_name}", "root", "Password1")
    # create abstract class onion
    orientdb_client.command("CREATE CLASS onion EXTENDS V ABSTRACT")
    # create mandatory property URL
    orientdb_client.command("CREATE PROPERTY onion.URL STRING")
    # create mandatory property URL
    orientdb_client.command("CREATE PROPERTY onion.ALIVE Boolean")
    # create class active
    orientdb_client.command("CREATE CLASS Active EXTENDS onion")
    # create property for active class
    orientdb_client.command("CREATE PROPERTY Active.HTTP_RESPONSE STRING")
    # create property for active class
    orientdb_client.command("CREATE PROPERTY Active.HASH_Content STRING")
    # create edge class LinkTo
    orientdb_client.command("CREATE CLASS LinkoTo EXTENDS E")
    # create
    orientdb_client.command("CREATE PROPERTY LinkoTo.appearances Integer")

    # create class inactive
    #orientdb_client.command("CREATE CLASS Inactive EXTENDS onion")


orientdb_client = pyorient.OrientDB("localhost", 2424) # host, port

# open a connection (username and password)
session_id = orientdb_client.connect("root", "Password1")

db_name = "Darknet"
initGraphDB(db_name)
