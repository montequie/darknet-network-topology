import pyorient
import os

onions_path = r'/home/talmoran/darknet/'
orientdb_client = pyorient.OrientDB("localhost", 2424) # host, port

# open a connection (username and password)
session_id = orientdb_client.connect("root", "Montequie#39")

db_name = "Darknet"

orientdb_client.db_open(db_name, "root", "Montequie#39")
#cluster_id = input("enter cluster ")
clusters = ["darknet_103",
"darknet_105",
"darknet_107",
"darknet_63",
"darknet_65",
"darknet_67",
"darknet_69",
"darknet_71",
"darknet_73",
"darknet_75",
"darknet_77",
"darknet_79",
"darknet_81",
"darknet_83",
"darknet_85",
"darknet_89",
"darknet_91",
"darknet_93",
"darknet_95",
"darknet_97"]


output = 'Cluster,Nodes,Active,Inactive,Total In-deg,Total Out-deg,Components\n'
components_output = ""
for cluster_id in clusters:
    active = orientdb_client.command(F"select count(*) from CLUSTER:{cluster_id} where ALIVE = true")[0].oRecordData['count']
    inactive = orientdb_client.command(F"select count(*) from CLUSTER:{cluster_id} where ALIVE = false")[0].oRecordData['count']
    # in/out deg
    indeg = orientdb_client.command(F"select in().size() as size from CLUSTER:{cluster_id} where ALIVE = true order by size desc")
    total_in_deg = 0
    for v in indeg:
        total_in_deg += v.oRecordData['size']
    outdeg = orientdb_client.command(F"select out().size() as size from CLUSTER:{cluster_id} where ALIVE = true order by size desc")
    total_out_deg = 0
    for v in outdeg:
        total_out_deg += v.oRecordData['size']
    # components
    onions = orientdb_client.command(F"select * from CLUSTER:{cluster_id} where ALIVE = true")
    # set of sets
    components = set()
    for onion in onions:
        # preform dfs from each node
        comp = orientdb_client.command(F"traverse out('LinkoTo'), outE('LinkoTo') from {onion._rid}")
        current_comp = set()
        for v in comp:
            # skip the edges return from the traverse
            if v._class != 'LinkoTo':
                current_comp.add(v.oRecordData['URL'])
        components.add(frozenset(current_comp))

    # check subset of to remove subset components
    components_list = list(components)
    for comp in components_list:
        for c in components_list:
            if comp != c:
                if comp.issubset(c):
                    components_list.remove(comp)
                    break
    output += F"{cluster_id}, {active + inactive}, {active}, {inactive}, {total_in_deg}, {total_out_deg}, {len(components_list)}\n"
    print(F"active onions {active}, inactive onions {inactive}")

with open(os.path.join(onions_path, 'cluster_output.csv'), 'w') as f:
    f.write(output)