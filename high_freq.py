import requests
import os
import pyorient
import queue
import threading
from dataclasses import dataclass, field
from typing import Any
import hashlib
import random

MINIMUM_SAMPLES = 330
MAXIMUM_SAMPLES = 660
NODES = 1000
LAST_OFFS_SAMPLE = 110 # off for one day


onions_path = r'/home/talmoran/darknet/complete'

session = requests.session()
session.proxies = {'http':  'socks5h://localhost:9050',
                   'https': 'socks5h://localhost:9050'}

orientdb_client = pyorient.OrientDB("localhost", 2424) # host, port
# open a connection (username and password)
session_id = orientdb_client.connect("root", "Password1")
# select to use that database
orientdb_client.db_open("Darknet", "root", "Password1")


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


class highfreq_obj:
    def __init__(self, url):
        self.url = url
        self.clusters = []
        self.on_current = 1
        self.on_durations = []
        # init the first duration
        self.on_durations.append(self.on_current)
        self.off_current = 0
        self.off_durations = []
        # True if on, False if off
        self.state = True
        # (on, off)
        self.transitions = (1,0)
        self.classification = -1


    def add_cluster(self, cluster):
        self.clusters.append(cluster)


    def add_on(self):
        if not self.state:
            self.on_durations.append(self.on_current)
            on, off = self.transitions
            self.transitions = (on + 1, off)
            self.state = True
            self.on_current = 1
            self.off_current = 1
        else:
            self.on_current += 1
            # update the last element
            self.on_durations[-1] = (self.on_current)


    def add_off(self):
        if self.state:
            self.off_durations.append(self.off_current)
            on, off = self.transitions
            self.transitions = (on, off + 1)
            self.state = False
            self.off_current = 1
            self.on_current = 1
        else:
            self.off_current += 1
            # update the last element
            self.off_durations[-1] = (self.off_current)


    # add durations, average
    def to_list(self):
        output = []
        output.append(f'URL~{self.url}\n')
        output.append(f'Classification~{self.classification}\n')
        output.append(f'On~{sum(self.on_durations)}\n')
        on_avg, off_avg = self.avg_duration()
        output.append(f'On duration average~{on_avg}\n')
        output.append(f'Off~{sum(self.off_durations)}\n')
        output.append(f'Off duration average~{off_avg}\n')
        output.append(f'Transitions~{self.transitions}\n')
        output.append(f'On duration~{str(self.on_durations)}\n')
        output.append(f'Sum on duration~{sum(onion.on_durations)}\n')
        output.append(f'Scans~{len(onion.clusters)}\n')
        output.append(f'Off duration~{str(self.off_durations)}\n')
        output.append(f'Clusters~')
        for cluster in self.clusters:
            output.append(f' {cluster}')

        '''
        output.append(f'\nAvailability~')
        availability = ''
        for cluster in self.clusters:
            alive = orientdb_client.command(F"select ALIVE from CLUSTER:{cluster} WHERE URL = '{onion.url}'")[0].ALIVE
            if alive:
                availability += '1,'
            else:
                availability += '0,'
        output.append(availability)
        '''
        return output

    def avg_duration(self):
        # + 1 for the current duration
        on_avg = sum(self.on_durations) / len(self.on_durations)
        off_avg = sum(self.off_durations) / len(self.on_durations)
        return on_avg, off_avg


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

    vertex_cluster_id = orientdb_client.data_cluster_add(F"high_freq_{vertex_id}", pyorient.CLUSTER_TYPE_PHYSICAL)
    orientdb_client.command(F"ALTER CLASS {cluster_class} ADDCLUSTER {vertex_cluster_id}")
    return F"high_freq_{vertex_id}"


def truncate_cluster(cluster_name):
    # truncate the db
    orientdb_client.command(F"truncate cluster {cluster_name} unsafe")


def is_vertex_exist(onion):
    #if len(orientdb_client.command(F"select from Active where URL='{onion}'")) == 0:
    if len(orientdb_client.command(F"select from CLUSTER:{vertex_cluster} where URL='{onion}'")) == 0:
        return False
    return True


def get_vertex(onion):
    # get the vertex object, SELECT return list - that's why we take [0]
    return orientdb_client.command(F"select from CLUSTER:{vertex_cluster} where URL='{onion}'")[0]


# TODO: check if succeeded
def insert_vertex(cluster, onion, state, hash_content, content = ''):
    return orientdb_client.command(F"insert into ACTIVE CLUSTER {cluster} (HTTP_Response, URL, ALIVE, HASH_Content) values('{content}', '{onion}', {state}, '{hash_content}')")



def create_edge(source, destination, appearances, cluster):
    orientdb_client.command(F"create edge LinkoTo CLUSTER {cluster} from {source} to {destination} SET appearances = '{appearances}'")


def set_active(rid):
    orientdb_client.command(F"update {rid} set ALIVE = True")


def move_class_to_inactive():
    inactive_onions_list = orientdb_client.command(F"select from Active where ALIVE='false'")
    for inactive_onion in inactive_onions_list:
        # move vertex #30:0 to class:Active
        orientdb_client.command(F"move vertex {inactive_onion._rid} to class:Inactive")

# if flag is True, we must classify
def classify_onion(onion, flag):
    avg_on, avg_off = onion.avg_duration()
    # Nearly always on - previous classification:
    # An alternate criterion could be to look at nodes that have no OFF period greater than, say, 2,
    # a majority, say 75% or more, of OFF periods that are of size 1,
    # and that is ON more than 50% of the time.

    # Nearly always on - current classification:
    # average off time smaller then 0.65; the average off time of classification 3 in our previous experiment was 0.585
    # the fraction of on time out of total scans is larger then 0.8; the average was 0.83237
    # TODO: keep the max ratio
    if  avg_off < 0.65 and sum(onion.on_durations) > len(onion.clusters) * 0.8:
        onion.classification = 1
        return 1
    # Started as on, and went off and never came back
    #  any node that has been ON before, and has now been OFF for more than a day
    elif onion.off_current > LAST_OFFS_SAMPLE:
        onion.classification = 2
        return 2
    # Nodes that are on and off for some period of time
    elif flag:
        onion.classification = 3
        return 3
    # no classification was found
    else:
        return -1

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
            #TODO: crawl to internal links
            if page.status_code == 200:

                onion_object.set_alive(True)
                try:
                    onion_object.set_hash(hashlib.sha224(page.content).hexdigest())
                except:
                    pass

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
                    # TODO: trim '-'; example - 'deepd­ot­­35w­­­vmeyd5.onion'
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

                        #onion_init_set.append(onion_link + '\n')

                    # get the discovered onion vertex object
                    discovered_onion_vertex = get_vertex(onion_link)

                    # create edge between current and discovered onion, weight is number of appearances of discovered
                    create_edge(current_onion_vertex._rid, discovered_onion_vertex._rid, onion.links[onion_link], edge_cluster)
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


previous_cluster = 'darknet_135'
# the active onions from last scan - as orientdb objects
live_onions = orientdb_client.command(F"select * from CLUSTER:{previous_cluster} where ALIVE = true")
for live_onion in live_onions:
    try:
        if live_onion.URL[-1] == '/':
            live_onion.URL = live_onion.URL[:-1]
    except:
        live_onions.remove(live_onion)
# list of the active onion urls
live_onions_urls = []
for onion in live_onions:
    live_onions_urls.append(highfreq_obj(onion.URL))

# choose randomly #NODES onions for the initial seed set
working_onions = random.sample(live_onions_urls, NODES)

# the onions that will be chosen later, after those in the initial set are done
onion_later_set = list(set(live_onions_urls) - set(working_onions))
classified_onions = []

while True:
    # TODO: implement select crawl
    vertex_cluster = createCluster("ACTIVE")
    edge_cluster = createCluster("LinkoTo")

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
    for onion_queue_item in working_onions:
        # The lowest valued entries are retrieved first
        q.put((1, onion_queue_item.url))
        sync_hashmap[onion_queue_item] = 1



    # the thread
    db_handler_t = threading.Thread(target=orientdb_handler)
    db_handler_t.start()

    # block until all tasks are done
    q.join()

    # stop workers
    for j in range(num_worker_threads):
        #TODO: change 3 to longest_depth + 1
        q.put((3, None))
    for t in threads:
        t.join()

    v.join()
    db_handler_t.join()
    temp_onions = []
    for onion in working_onions:
        onion_path = os.path.join(onions_path, f"{onion}.txt")

        onion.add_cluster(vertex_cluster)
        alive = orientdb_client.command(F"select ALIVE from CLUSTER:{vertex_cluster} WHERE URL = '{onion.url}'")[0].ALIVE
        if alive:
            onion.add_on()
        else:
            onion.add_off()
        # if we already collected maximum number of samples
        classify_flag = len(onion.clusters) == MAXIMUM_SAMPLES
        # if we collected enough samples to try to classify and the classification resulted something
        if len(onion.clusters) >= MINIMUM_SAMPLES and classify_onion(onion, classify_flag) != -1:
                working_onions.remove(onion)
                classified_onions.append(onion)
                # write the classification of the onion
                with open(os.path.join(onions_path, f'{onion.url}.txt'), 'w') as f:
                    f.writelines(onion.to_list())
                if len(onion_later_set) != 0:
                    new_onion = random.sample(onion_later_set, 1)
                    onion_later_set.remove(new_onion[0])
                    temp_onions.extend(new_onion)
    working_onions.extend(temp_onions)
    if len(working_onions) == 0: break

# TODO: csv the classified onions
