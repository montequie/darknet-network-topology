import requests
import os
import pyorient
from lxml import html
import queue
import collections
import re
import threading
from dataclasses import dataclass, field
from typing import Any
import hashlib


class onion_obj:
    def __init__(self, url):
        self.url = url
        self.links = {}
        self.alive = False
        self.hash = ''

    def set_links(self, links):
        self.links = links

    def set_alive(self, alive):
        self.alive = alive

    def set_hash(self, hash):
        self.hash = hash


# used for the priority queue
@dataclass(order=True)
class PrioritizedItem:
    priority: int
    item: Any = field(compare=False)


def createCluster(cluster_class):
    vertex_id = 1
    try:
        while orientdb_client.data_cluster_count([vertex_id]) >= 0:
            vertex_id += 1
    except pyorient.exceptions.PyOrientDatabaseException:
        pass
    # create a new cluster
    vertex_cluster_id = orientdb_client.data_cluster_add(F"darknet_{vertex_id}", pyorient.CLUSTER_TYPE_PHYSICAL)
    orientdb_client.command(F"ALTER CLASS {cluster_class} ADDCLUSTER {vertex_cluster_id}")
    return F"darknet_{vertex_id}"


def truncate_cluster(cluster_name):
    # truncate the db
    orientdb_client.command(F"truncate cluster {cluster_name} unsafe")


def is_vertex_exist(onion):
    # if len(orientdb_client.command(F"select from Active where URL='{onion}'")) == 0:
    if len(orientdb_client.command(F"select from CLUSTER:{vertex_cluster} where URL='{onion}'")) == 0:
        return False
    return True


def get_vertex(onion):
    # get the vertex object, SELECT return list - that's why we take [0]
    return orientdb_client.command(F"select from CLUSTER:{vertex_cluster} where URL='{onion}'")[0]


def insert_vertex(cluster, onion, state, hash_content, content=''):
    return orientdb_client.command(
        F"insert into ACTIVE CLUSTER {cluster} (HTTP_Response, URL, ALIVE, HASH_Content) values('{content}', '{onion}', {state}, '{hash_content}')")


def create_edge(source, destination, appearances, cluster):
    orientdb_client.command(
        F"create edge LinkoTo CLUSTER {cluster} from {source} to {destination} SET appearances = '{appearances}'")


def set_active(rid):
    orientdb_client.command(F"update {rid} set ALIVE = True")


def move_class_to_inactive():
    inactive_onions_list = orientdb_client.command(F"select from Active where ALIVE='false'")
    for inactive_onion in inactive_onions_list:
        orientdb_client.command(F"move vertex {inactive_onion._rid} to class:Inactive")


def crawler():
    while True:
        priority, onion = q.get()

        if onion is None:
            # indicate 1 worker has finished
            v.put(None)
            # take out the None
            q.task_done()
            break

        # orientDB doesn't cooperate well with the threaded crawlers,
        # so this object will put in a queue and be handled by 1 worker
        onion_object = onion_obj(onion)

        # add the url to the
        sync_hashmap[onion_object.url] = 1

        try:
            # send get request to the onion
            page = session.get(F"http://{str(onion_object.url)}", timeout=5)
            if page.status_code == 200:

                onion_object.set_alive(True)

                try:
                    # parse HTTP_Response
                    tree = html.fromstring(page.content)

                    onion_object.set_hash(hashlib.sha224(page.content).hexdigest())

                    # using XPath, extracting all the links
                    onion_links = tree.xpath('//a/@href')

                except:
                    onion_links = []
                    pass

                # a list that holds the trimmed onion links, only "[a-zA-z0-9]{16}.onion"
                onion_links_trimmed = []

                # trim the URL, remove strings after .onion
                for onion_link in onion_links:
                    result = re.match(r"(.*)([a-zA-z0-9]{16}.onion)", onion_link)
                    # internal_onion = re.match(r"(.*)([a-zA-z0-9]{16}.onion[\/A-Za-z0-9]*)", onion_link)
                    if result != None:
                        # group 2 indicates to - ([a-zA-z0-9]{16}.onion)
                        onion_links_trimmed.append(str(result.group(2)))
                    # if internal_onion != None:
                    #    if not internal_onion in sync_internals_links:
                    #        sync_internals_links[internal_onion] = 1

                # converting the trimmed list to a dict, the keys are the links and the values are the appearances of each link
                onion_links_dict = collections.Counter(onion_links_trimmed)

                onion_object.set_links(onion_links_dict.copy())

                for onion_link in onion_links_dict.keys():
                    # add vertex to the queue only if it's not in the graph already
                    if not onion_link in sync_hashmap:
                        # add the url to the
                        sync_hashmap[onion_link] = 1
                        # add link to queue
                        q.put((2, onion_link))
        except requests.exceptions.RequestException as e:
            onion_object.set_alive(False)

        # insert the onion object into the vertices list
        v.put(onion_object)

        # finish the current task - the current onion
        q.task_done()


def orientdb_handler():
    none_counter = 0
    while none_counter < num_worker_threads:
        onion = v.get()
        if onion is None:
            none_counter = none_counter + 1
        elif onion.alive:
            try:
                # check if the vertex existence
                if not is_vertex_exist(onion.url):
                    # insert vertex
                    insert_vertex(vertex_cluster, onion.url, 'true', onion.hash)
                # get the vertex object
                current_onion_vertex = get_vertex(onion.url)

                # update his state to active
                set_active(current_onion_vertex._rid)

                for onion_link in onion.links.keys():
                    if not is_vertex_exist(onion_link):
                        # insert discovered vertex with state = false
                        insert_vertex(vertex_cluster, onion_link, 'false', onion.hash)

                        # onion_init_set.append(onion_link + '\n')

                    # get the discovered onion vertex object
                    discovered_onion_vertex = get_vertex(onion_link)

                    # create edge between current and discovered onion, weight is number of appearances of discovered
                    create_edge(current_onion_vertex._rid, discovered_onion_vertex._rid, onion.links[onion_link],
                                edge_cluster)
            except:
                pass
        else:
            try:
                if not is_vertex_exist(onion.url):
                    # insert vertex
                    insert_vertex(vertex_cluster, onion.url, 'false', onion.hash)
            except:
                pass
        v.task_done()


onions_path = r'/home/talmoran/darknet/'
session = requests.session()
session.proxies = {'http': 'socks5h://localhost:9050',
                   'https': 'socks5h://localhost:9050'}

orientdb_client = pyorient.OrientDB("localhost", 2424)  # host, port

# open a connection (username and password)
session_id = orientdb_client.connect("root", "Montequie#39")

# select to use that database
orientdb_client.db_open("Darknet", "root", "Montequie#39")

while True:
    vertex_cluster = createCluster("ACTIVE")
    edge_cluster = createCluster("LinkoTo")
    clusters = []
    clusters.append(F"Vertex cluster - {vertex_cluster}")
    clusters.append(F"Edge cluster - {edge_cluster}")
    with open(os.path.join(onions_path, F"{vertex_cluster}.txt"), 'w') as f:
        f.writelines(clusters)

    onion_init_set = []

    with open(os.path.join(onions_path, 'full_scans', 'onions_super_list.txt'), 'r') as f:
        onion_init_set = f.readlines()

    # A synchronized priority queue class, contains onion links
    q = queue.PriorityQueue()

    # vertices queue, contains onion objects
    v = queue.Queue()

    sync_hashmap = {}
    sync_internals_links = {}

    threads = []
    num_worker_threads = 5

    for j in range(num_worker_threads):
        t = threading.Thread(target=crawler)
        threads.append(t)
        t.start()

    # insert seed nodes
    for onion_queue_item in onion_init_set:
        # The lowest valued entries are retrieved first
        q.put((1, onion_queue_item[:-1]))
        sync_hashmap[onion_queue_item[:-1]] = 1

    # the thread
    db_handler_t = threading.Thread(target=orientdb_handler)
    db_handler_t.start()

    # block until all tasks are done
    q.join()

    # stop workers
    for j in range(num_worker_threads):
        q.put((3, None))
    for t in threads:
        t.join()

    v.join()
    db_handler_t.join()

    live_onions = orientdb_client.command(F"select * from CLUSTER:{vertex_cluster} where ALIVE = true")
    for live_onion in live_onions:
        onion_init_set.append(live_onion.URL)
    # trim onions with '/' in the url - to remove duplicates
    for onion in onion_init_set:
        if onion[-1] == '\n' and onion[-2] == '/':
            onion_init_set.remove(onion)
            onion_init_set.append(F"{onion[:-2]}\n")
        elif onion[:-1] == '/':
            onion_init_set.remove(onion)
            onion_init_set.append(F"{onion[:-1]}\n")

    with open(os.path.join(onions_path, 'full_scans', 'onions_super_list.txt'), 'w') as f:
        f.writelines(set(onion_init_set))