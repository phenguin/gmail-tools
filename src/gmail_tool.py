#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals
from __future__ import print_function

import apiclient
import argparse
import concurrent.futures
import contextlib
import googleapiclient
import httplib2
import itertools as it
import os
import os.path
import pickle
import re
import sys
import threading

import logging
logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))
log = logging.getLogger(__name__)

from concurrent.futures import ThreadPoolExecutor
from googleapiclient.discovery import build
from googleapiclient.http import HttpRequest
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
"""
Performs basic bulk operations on gmail using oauth.
"""

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# SIGINT handling for C-c.
import signal


def signal_handler(sig, frame):
    print('C-c caught.  Exiting..')
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


def _Batched(iterable, batch_size=50, fillvalue=None):
    "grouper(3, 'ABCDEFG', 'x') --> ABC DEF Gxx"
    args = [iter(iterable)] * batch_size
    return it.izip_longest(fillvalue=fillvalue, *args)


class GmailService(threading.local):

    def __init__(self, batch_size=50):
        self._credentials = None
        self._service = self.get_gmail_service()
        log
        self._labels = {}
        self._batch_size = batch_size

    def get_gmail_service(self):
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                self._credentials = pickle.load(token)
                # If there are no (valid) credentials available, let the user log in.
        if not self._credentials or not self._credentials.valid:
            if self._credentials and self._credentials.expired and self._credentials.refresh_token:
                self._credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                self._credentials = flow.run_local_server()
            # Save the credentials for the next run
            with open('token.pickle', 'wb') as token:
                pickle.dump(self._credentials, token)

        return build(
            'gmail', 'v1', credentials=self._credentials, cache_discovery=False)

    def MakeModifyThread(self,
                         thread_id,
                         remove_labels=None,
                         add_labels=None,
                         fields='id',
                         user_id='me'):
        remove_labels = remove_labels or []
        add_labels = add_labels or []
        body = {
            'removeLabelIds': remove_labels,
            'addLabelIds': add_labels,
        }
        return self._service.users().threads().modify(
            userId=user_id, fields=fields, id=thread_id, body=body)

    def ModifyThreadsCallback(self, *args):
        pass

    def ModifyThreads(self,
                      thread_ids,
                      remove_labels=None,
                      add_labels=None,
                      fields='id',
                      user_id='me'):
        batch = self._service.new_batch_http_request(self.ModifyThreadsCallback)
        for thread_id in thread_ids:
            batch.add(
                self.MakeModifyThread(
                    thread_id,
                    remove_labels=remove_labels,
                    add_labels=add_labels,
                    fields=fields,
                    user_id=user_id))
            # FIXME: Can I pass this to
        batch.execute()
        return len(thread_ids)

    def ListMessages(self,
                    label_ids=[],
                    query='',
                    user_id='me',
                    fields='nextPageToken,messages/id',
                    max_results=None):
        def get_response(page_token=None):
            log.info(
                "Querying gmail for message_ids matching query: %s" % (query,))
            result = service.users().messages().list(
                userId=user_id,
                fields=fields,
                q=query,
                labelIds=label_ids,
                pageToken=page_token).execute(num_retries=5)
            log.info(
                "Got %s matching messages back!" % (len(result['messages']),))
            return result

        service = self._service
        try:
            i = 0
            response = get_response()
            if 'messages' in response:
                for message in response['messages']:
                    yield message
                    i += 1

            while 'nextPageToken' in response:
                if max_results is not None and i > max_results: break
                page_token = response['nextPageToken']
                response = get_response(page_token=page_token)
                for message in response['messages']:
                    yield message
                    i += 1
        except apiclient.errors.HttpError, error:
            log.error('An error occurred: %s' % error)

    def ListThreads(self,
                    label_ids=[],
                    query='',
                    user_id='me',
                    fields='nextPageToken,messages/id',
                    max_results=None):
        def get_response(page_token=None):
            log.info(
                "Querying gmail for thread_ids matching query: %s" % (query,))
            result = service.users().threads().list(
                userId=user_id,
                fields=fields,
                q=query,
                labelIds=label_ids,
                pageToken=page_token).execute(num_retries=5)
            log.info(
                "Got %s matching threads back!" % (len(result['threads']),))
            return result

        service = self._service
        try:
            i = 0
            response = get_response()
            if 'threads' in response:
                for thread in response['threads']:
                    yield thread
                    i += 1

            while 'nextPageToken' in response:
                if max_results is not None and i > max_results: break
                page_token = response['nextPageToken']
                response = get_response(page_token=page_token)
                for thread in response['threads']:
                    yield thread
                    i += 1
        except apiclient.errors.HttpError, error:
            log.error('An error occurred: %s' % error)

    def ListLabels(self):
        # Call the Gmail API
        results = self._service.users().labels().list(userId='me').execute()
        labels = results.get('labels', [])
        for label in labels:
            yield label


def create_parser():
    parser = argparse.ArgumentParser()
    parser.set_defaults(action='query')
    parser.add_argument('-n', '--dry-run', action='store_true', default=False)
    # Actions
    parser.add_argument(
        '--list_threads',
        dest='action',
        action='store_const',
        const='list_threads')
    parser.add_argument(
        '--list_messages',
        dest='action',
        action='store_const',
        const='list_messages')
    parser.add_argument(
        '--labels', dest='action', action='store_const', const='labels')
    parser.add_argument(
        '--modify', dest='action', action='store_const', const='modify')
    # Arguments for querying threads.
    parser.add_argument('-q', '--query', type=str, default='')
    parser.add_argument('--max_results', type=int)

    def comma_delimeted(x):
        if x is None: return []
        return x.split(',')

    parser.add_argument('--add-labels', type=comma_delimeted)
    parser.add_argument('--remove-labels', type=comma_delimeted)
    parser.add_argument('--batch-size', type=int, default=50)
    parser.add_argument('--max-inflight-batches', type=int, default=10)
    parser.add_argument('--max-pool-workers', type=int, default=4)
    return parser


def list_threads_handler(gmail, query, max_results=None):
    threads = gmail.ListThreads(query=query, max_results=max_results)
    for thread in threads:
        print(thread)

def list_messages_handler(gmail, query, max_results=None):
    messages = gmail.ListMessages(query=query, max_results=max_results)
    for message in messages:
        print(message)


class BoundedExecutor(concurrent.futures.Executor):

    def __init__(self, max_workers=None, max_inflight=4):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._lock = threading.Lock()
        self._total_processed = 0
        self._sem = threading.BoundedSemaphore(max_inflight)

    def _acquire(self):
        return self._sem.acquire(True)

    def _done_cb(self, future):
        self._sem.release()
        if future.exception() is not None:
            log.error("Got exception in done callback!")
            raise future.exception()
        processed = future.result()
        with self._lock:
            self._total_processed += processed
            total = self._total_processed
        log.info("Successfully updated %s threads (%s cumulatively)!" %
                 (processed, total))

    def __enter__(self):
        self._executor.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is KeyboardInterrupt:
            logging.warning("Got interrupt signal!  Exiting..")
            sys.exit(0)
        return super(BoundedExecutor, self).__exit__(exc_type, exc_value,
                                                     traceback)

    # def total_processed(self):
    #   with self._lock:
    #     return self._total_processed

    def submit(self, fn, *args, **kwargs):
        self._acquire()
        future = self._executor.submit(fn, *args, **kwargs)
        future.add_done_callback(self._done_cb)
        return future

    def shutdown(self, wait=True):
        return self._executor.shutdown(wait=wait)


def modify_threads_handler(gmail, query, add_labels, remove_labels, max_results,
                           dry_run, batch_size, max_inflight_batches,
                           max_pool_workers):
    threads = gmail.ListThreads(query=query, max_results=max_results)
    with BoundedExecutor(max_pool_workers, max_inflight_batches) as pool:
        for batch in _Batched(threads, batch_size=batch_size):
            if dry_run:
                log.warning(
                    'DRYRUN: Not modifying %s threads..' % (len(batch,)))
            else:
                log.info(
                    "Sending thread modification request for batch of thread_ids.."
                )
                pool.submit(
                    gmail.ModifyThreads,
                    [t['id'] for t in batch if t is not None],
                    add_labels=add_labels,
                    remove_labels=remove_labels)


def handle(args):
    gmail = GmailService()

    if args.action == 'list_threads':
        list_threads_handler(gmail, args.query, args.max_results)
    if args.action == 'list_messages':
        list_messages_handler(gmail, args.query, args.max_results)
    elif args.action == 'labels':
        for label in gmail.ListLabels():
            print(label)
    elif args.action == 'modify':
        modify_threads_handler(gmail, args.query, args.add_labels,
                               args.remove_labels, args.max_results,
                               args.dry_run, args.batch_size,
                               args.max_inflight_batches, args.max_pool_workers)
    else:
        raise argparse.ArgumentError('%r not recognized' % args.action)


def main():
    args = create_parser().parse_args()
    return handle(args)


if __name__ == '__main__':
    main()
