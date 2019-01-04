import pyorient
import random
import os
import statistics
from decimal import Decimal as D

onions_path = r'/Users/montequie/Dropbox/IDC - CS/WashU/Darknet/torPOC/'

orientdb_client = pyorient.OrientDB("localhost", 2424) # host, port

# open a connection (username and password)
session_id = orientdb_client.connect("root", "Password1")

#TODO: make sure the db is created / exist

# select to use that database
orientdb_client.db_open("Darknet", "root", "Password1")

# TODO: implement select crawl
#active_cluster_id, inactive_cluster_id = createClusters()
active_cluster, inactive_cluster = 'darknet_41', 'crawl_5'
edge_cluster = 'darknet_42'

# key is root of graph, values are nodes discovered in DFS
onions_dfs = {}

# get all vertexes rid
onions = orientdb_client.command(F"select * from CLUSTER:{active_cluster} where ALIVE = true")
for onion in onions:
    # list of tuples (url, alive)
    discoverd_onions = []
    dfs_onions = orientdb_client.command(F"traverse out('LinkoTo'), outE('LinkoTo') from {onion._rid}")
    for dfs_onion in dfs_onions:
        if dfs_onion._class == 'Active':
            discoverd_onions.append((dfs_onion.URL, dfs_onion.ALIVE))
    onions_dfs[onion.URL] = discoverd_onions

output = 'Groups Size,Discovered,Active,Inactive\n'
avg_output = 'Groups Size,Active,Inactive,Discovered,Standard Deviation,Variance\n'
base_group_size = 25
# shuffle X rid
for i in range (1, 26):
    discovered_avg = 0
    discovered_stdev = []
    active_avg = 0
    inactive_avg = 0
    for j in range(0, 100):
        #
        onions_dfs_list = []
        active = 0
        inactive = 0
        onions_dfs_counter = 0
        # get i * j keys from the onion_dfs dict
        onions_urls = random.sample(list(onions_dfs), i * base_group_size)
        for url in onions_urls:
            onions_dfs_list += onions_dfs[url]
        for onion, state in set(onions_dfs_list):
            if state:
                active += 1
            else:
                inactive += 1
        onions_dfs_counter = len(set(onions_dfs_list))
        # group size, discovered onions from this, Active, Not Active
        output += F"{i * base_group_size}, {onions_dfs_counter}, {active}, {inactive}\n"
        discovered_stdev.append(D(onions_dfs_counter))
        discovered_avg += onions_dfs_counter
        active_avg += active
        inactive_avg += inactive

    avg_output += F"{i * base_group_size}, {active_avg / j}, {inactive_avg / j}, {discovered_avg / j}, {statistics.stdev(discovered_stdev)},{statistics.variance(discovered_stdev)}\n"
#TODO calc avg
with open(os.path.join(onions_path, 'dfs_output.csv'), 'w') as f:
    f.write(output)
with open(os.path.join(onions_path, 'dfs_output_avg.csv'), 'w') as f:
    f.write(avg_output)
