import requests
import os
from lxml import html
import queue
import re
import threading
from dataclasses import dataclass, field
from typing import Any
from requests.adapters import HTTPAdapter
from urllib3 import Retry

def requests_retry_session(
    retries=3,
    backoff_factor=0.3,
    status_forcelist=(500, 502, 504),
    session=None,
):
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


onions_path = r'/Users/montequie/Dropbox/IDC - CS/WashU/Darknet/torPOC/'
session = requests_retry_session()
MAX_DEPTH = 8
MAX_CRAWLS = 50000

# used for the priority queue
@dataclass(order=True)
class PrioritizedItem:
    priority: int
    item: Any = field(compare=False)


def crawl():
    while True:
        #TODO: maybe change depth to depth
        depth, url = sources.get()

        if url is None:
            # take out the None
            sources.task_done()
            break

        if depth > MAX_DEPTH:
            pass
        else:
            try:

                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36',
                }
                # send get request to the onion
                page = session.get(F"{str(url)}", timeout=5, headers=headers)
                #page = session.get(F"{str(url)}", timeout=5 )
                if page.status_code == 200:

                    # parse HTTP_Response
                    tree = html.fromstring(page.content)

                    # using XPath, extracting all the links
                    links = tree.xpath('//a/@href')

                    # trim the URL, remove strings after .onion
                    for link in links:
                        result = re.match(r"(.*)([a-zA-z0-9]{16}\.onion)", link)
                        internal_link = re.match(r"^(/|#|\?).*", link)
                        if result != None:
                            # group 2 indicates to - ([a-zA-z0-9]{16}.onion)
                            onion_links.append(F"{str(result.group(2))}\n")
                        elif internal_link != None:
                            link = F"{url}/{internal_link.group(0)}"
                        if not link in sync_hashmap and len(sync_hashmap) < MAX_CRAWLS:
                        #if not link in sync_hashmap:
                            sync_hashmap[link] = 1
                            sources.put((depth + 1, link))
            except:
                pass
        # finish the current task - the current source
        sources.task_done()


with open(os.path.join(onions_path, 'onion_web_resources.txt'), 'r') as f:
    onion_sources = set(f.readlines())



# A synchronized priority queue class, contains onion links
sources = queue.PriorityQueue()

sync_hashmap = {}
onion_links = []

# keeping the old onions
with open(os.path.join(onions_path, 'ahmia_fi_onions.txt'), 'r') as f:
    ahmia_set = set(f.readlines())
    for onion in ahmia_set:
        onion_links.append(onion)
with open(os.path.join(onions_path, 'onions_super_list.txt'), 'r') as f:
    old_set = set(f.readlines())
    for onion in old_set:
        onion_links.append(onion)
print(F"old set size - {len(set(onion_links))}")

threads = []
num_worker_threads = 10

for j in range(num_worker_threads):
    t = threading.Thread(target=crawl)
    threads.append(t)
    t.start()

# insert seed nodes
for source in onion_sources:
    sync_hashmap[source] = 1
    # The lowest valued entries are retrieved first
    sources.put((1, source))


# block until all tasks are done
sources.join()

# stop workers
for j in range(num_worker_threads):
    sources.put((MAX_DEPTH, None))
for t in threads:
    t.join()

with open(os.path.join(onions_path, 'onions_super_list.txt'), 'w') as f:
    f.writelines(set(onion_links))