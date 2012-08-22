from pylons import config
import urllib2
import couchdb
import json
from lr.model.resource_data_monitor import IncomingCopyHandler, CompactionHandler, UpdateViewsHandler
import copy
import logging
import uuid
import threading
import time
_DEFAULT_CHANGE_OPTIONS = {'feed': 'continuous',
                           'include_docs': True}
log = logging.getLogger(__name__)

s = couchdb.Server(config['couchdb.url.dbadmin'])


def get_design_docs(db):
    return db.view('_all_docs', include_docs=True, startkey='_design%2F', endkey='_design0')


def load_data():
    node = s[config['couchdb.db.node']]
    node_description = node['node_description']
    with open('lr/tests/data/nsdl_dc/data-000000000.json', 'r') as f:
        data = json.load(f)
    for doc in data['documents']:
        doc['publishing_node'] = node_description['node_id']
        doc['doc_ID'] = uuid.uuid1().hex
        doc['_id'] = doc['doc_ID']
    return data


def get_changes():
    incoming_database = s[config['couchdb.db.incoming']]
    last_change_sequence = incoming_database.info()['update_seq']
    change_settings = copy.deepcopy(_DEFAULT_CHANGE_OPTIONS)
    change_settings['since'] = last_change_sequence
    #ignore all documents currently in DB
    data = load_data()
    initial_doc_count = incoming_database.info()['doc_count']
    incoming_database.update(data['documents'])
    changes = incoming_database.changes(**change_settings)
    return changes, incoming_database, initial_doc_count


def delete_data(db, docs):
    for d in docs['documents']:
        del db[d['_id']]


def test_incoming_delete():
    handler = IncomingCopyHandler()
    changes, incoming_database, initial_doc_count = get_changes()
    prechanges_handler_thread_count = threading.activeCount()
    ids = []
    for change in changes:
        if 'doc' in change and 'doc_ID' in change['doc']:
            ids.append(change['doc']['doc_ID'])
        handler.handle(change, incoming_database)
    while threading.activeCount() > prechanges_handler_thread_count:
        time.sleep(.5)
    assert incoming_database.info()['doc_count'] == initial_doc_count
    resource_data_database = s[config['couchdb.db.resourcedata']]
    for i in ids:
        del resource_data_database[i]


def test_incoming_copy():
    handler = IncomingCopyHandler()
    resource_data_database = s[config['couchdb.db.resourcedata']]
    changes, incoming_database, initial_doc_count = get_changes()
    prechanges_handler_thread_count = threading.activeCount()
    ids = []
    for change in changes:
        if 'doc' in change and 'doc_ID' in change['doc']:
            ids.append(change['doc']['doc_ID'])
        handler.handle(change, incoming_database)
    while threading.activeCount() > prechanges_handler_thread_count:
        time.sleep(.5)
    for doc_id in ids:
        assert resource_data_database[doc_id] is not None


def test_compaction_handler():
    resource_data_database = s[config['couchdb.db.resourcedata']]
    data = load_data()
    resource_data_database.update(data['documents'])
    changes = resource_data_database.changes(**_DEFAULT_CHANGE_OPTIONS)
    did_compact_run = False
    designDocs = get_design_docs(resource_data_database)
    handler = CompactionHandler(10)
    count = 0
    for change in changes:
        count += 1
        handler.handle(change, resource_data_database)
        if count % 10 == 1:
            for designDoc in designDocs:
                viewInfo = "{0}/{1}/_info".format(resource_data_database.resource.url, designDoc.id)
                viewInfo = json.load(urllib2.urlopen(viewInfo))
                did_compact_run = did_compact_run or viewInfo['view_index']['compact_running']
                if did_compact_run:
                    break
    assert did_compact_run
    delete_data(resource_data_database, data)


def test_view_update_handler():
    handler = UpdateViewsHandler(10)
    resource_data_database = s[config['couchdb.db.resourcedata']]
    designDocs = get_design_docs(resource_data_database)
    changes = resource_data_database.changes(**_DEFAULT_CHANGE_OPTIONS)
    did_views_update = False
    data = load_data()
    resource_data_database.update(data['documents'])
    count = 0
    for change in changes:
        count += 1
        handler.handle(change, resource_data_database)
        if count % 10 == 1:
            for designDoc in designDocs:
                viewInfo = "{0}/{1}/_info".format(resource_data_database.resource.url, designDoc.id)
                viewInfo = json.load(urllib2.urlopen(viewInfo))
                did_views_update = did_views_update or viewInfo['view_index']['updater_running']
                if did_views_update:
                    break
    assert did_views_update
    delete_data(resource_data_database, data)
