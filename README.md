# gmail-tools

This is the result of a few days frustration of trying to re-organize my gmail
setup.  The final blocking issue was to "start fresh" and archive most of my
inbox.  Unfortunately my inbox is pretty huge, and the operations were failing
from the UI, so I decided to use the api.  I looked into several other similar
seeming tools, like [gmf](https://github.com/larsks/gmailfilters*), however
they all didn't quite work (lacking features, oauth support, etc).  

So here we are..

## Installation

### Dependencies
Maybe one day I'll polish this and package it better, but that day is not today.

```shellsession
 pip install --upgrade apiclient futures gmail-yaml-filters google-api-python-client google-auth google-auth-httplib2 google-auth-oauthlib progressbar requests
```
### Authentication
The authentication used here is mostly stolen from the google api
[quickstart guide](https://developers.google.com/sheets/api/quickstart/python).
Following the instructions there but replacing their script with this one should
do the trick.

## Usage

```shellsession
src/gmail_tool.py --help
```

