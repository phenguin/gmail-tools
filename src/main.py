#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals
from __future__ import print_function

import argparse
import os.path
import pickle
import re
import sys

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def get_gmail_service():
  print('Credendtials from environ: {}'.format(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')))
  creds = None
  # The file token.pickle stores the user's access and refresh tokens, and is
  # created automatically when the authorization flow completes for the first
  # time.
  if os.path.exists('token.pickle'):
    with open('token.pickle', 'rb') as token:
      creds = pickle.load(token)
      # If there are no (valid) credentials available, let the user log in.
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      creds.refresh(Request())
    else:
      flow = InstalledAppFlow.from_client_secrets_file(
          'credentials.json', SCOPES)
      creds = flow.run_local_server()
    # Save the credentials for the next run
    with open('token.pickle', 'wb') as token:
      pickle.dump(creds, token)

  return build('gmail', 'v1', credentials=creds)


class GmailService(object):
  def __init__(self):
    self._service = get_gmail_service()


  def GetLabels(self):
    # Call the Gmail API
    results = self._service.users().labels().list(userId='me').execute()
    labels = results.get('labels', [])
    for label in labels:
      yield label['name']

"""
Performs basic bulk operations on gmail using oauth.
"""

def create_parser():
  parser = argparse.ArgumentParser()
  parser.set_defaults(action='query')
  parser.add_argument('-n', '--dry-run', action='store_true', default=False)
  # Actions
  parser.add_argument('--query', dest='action', action='store_const', const='query')
  parser.add_argument('--labels', dest='action', action='store_const', const='labels')
  parser.add_argument('--archive', dest='action', action='store_const', const='archive')
  return parser

def handle(args):
  gmail = GmailService()

  if args.action == 'query':
    raise Exception("NYI")
  elif args.action == 'labels':
    for name in gmail.GetLabels():
      print(name)
  elif args.action == 'archive':
    raise Exception("NYI")
  else:
    raise argparse.ArgumentError('%r not recognized' % args.action)



def main():
  args = create_parser().parse_args()
  return handle(args)

if __name__ == '__main__':
  main()
