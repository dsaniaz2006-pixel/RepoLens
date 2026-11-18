"""Offline integration of trusted forwarded scheme at the loopback API boundary."""
import asyncio

from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware


def test_trusted_loopback_proxy_sets_https_for_oauth_callback_url():
    observed = []

    async def app(scope, receive, send):
        observed.append((scope.get('scheme'), scope.get('client')))
        await send({'type':'http.response.start','status':200,'headers':[]})
        await send({'type':'http.response.body','body':b'ok'})

    wrapped = ProxyHeadersMiddleware(app, trusted_hosts='127.0.0.1')

    async def visit(client):
        scope = {
            'type':'http','http_version':'1.1','method':'GET',
            'path':'/api/auth/callback/google',
            'scheme':'http','client':(client,55444),'server':('127.0.0.1',8000),
            'headers':[
                (b'host',b'127.0.0.1:5173'),
                (b'x-forwarded-proto',b'https'),
                (b'x-forwarded-for',b'127.0.0.1'),
            ],
        }
        async def receive():return {'type':'http.request','body':b'','more_body':False}
        async def send(_message):pass
        await wrapped(scope,receive,send)

    asyncio.run(visit('127.0.0.1'))
    assert observed[0][0]=='https', 'Trusted Vite proxy must preserve public HTTPS scheme'
    asyncio.run(visit('192.0.2.5'))
    assert observed[1][0]=='http', 'Untrusted external peer must not spoof the protocol'
