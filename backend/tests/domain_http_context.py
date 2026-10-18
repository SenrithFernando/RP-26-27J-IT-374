"""Explicit INTERNAL context for old loopback-only domain router test servers.

These servers test domain persistence, NOT authentication. main.app never imports
this module. Security tests mount actual main.app and perform genuine logins.
"""
from types import SimpleNamespace
from fastapi.responses import JSONResponse


def install_domain_context(app):
    @app.middleware('http')
    async def domain_test_context(request,call_next):
        if request.client and request.client.host not in ('127.0.0.1','::1','testclient'):
            return JSONResponse(status_code=403,content={'detail':'Internal loopback test server only.'})
        request.state.principal=SimpleNamespace(user=SimpleNamespace(id='internal-domain-test',role='administrator'),
            login=SimpleNamespace(mode='real'))
        return await call_next(request)
