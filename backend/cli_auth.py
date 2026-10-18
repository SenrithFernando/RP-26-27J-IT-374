"""Private terminal login for existing simulation tools. No credentials in argv/env."""
import atexit,json
from getpass import getpass
from urllib.request import Request,urlopen
_headers={}


def headers():return dict(_headers)


def configure(base_url,username=None):
    username=username or input('Account username: ').strip()
    password=getpass('Password (hidden): ')
    request=Request(base_url.rstrip('/')+'/auth/login',data=json.dumps({'username':username,'password':password,'mode':'demo'}).encode(),
        headers={'Content-Type':'application/json'},method='POST')
    with urlopen(request,timeout=15) as response:result=json.load(response)
    _headers['Authorization']='Bearer '+result['token']
    def logout():
        try:
            with urlopen(Request(base_url.rstrip('/')+'/auth/logout',data=b'',headers=_headers,method='POST'),timeout=3):pass
        except Exception:pass  # Server TTL still bounds a failed shutdown revocation.
        _headers.clear()
    atexit.register(logout)
