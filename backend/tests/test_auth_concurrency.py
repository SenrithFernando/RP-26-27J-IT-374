"""Authorization lock waits must leave the ASGI event loop responsive."""
import asyncio
from threading import Event
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch
from starlette.requests import Request
from auth import authorize


class AuthorizationConcurrencyTests(IsolatedAsyncioTestCase):
    async def test_blocking_authorization_does_not_stall_event_loop(self):
        entered,release=Event(),Event()
        def wait_for_lock(*args):
            entered.set()
            if not release.wait(2):
                raise AssertionError('Event loop could not release authorization wait')
        request=Request({'type':'http','method':'GET','path':'/auth/me','headers':[]})
        with patch('auth.authorize_sync',side_effect=wait_for_lock):
            task=asyncio.create_task(authorize(request,None,object()))
            try:
                for _ in range(100):
                    if entered.is_set():break
                    await asyncio.sleep(.01)
                self.assertTrue(entered.is_set())
                self.assertFalse(task.done())
            finally:
                release.set()
                await task
