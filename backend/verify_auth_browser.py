"""Run browser against actual main.app with rollback-only HTTP security fixtures."""
import json,os,socket,subprocess,sys,threading,time
from pathlib import Path
import uvicorn
sys.path.insert(0,str(Path(__file__).parent/'tests'))
from test_access_control import AccessControlTests
from main import app
from persistence import session_dependency


def main():
    AccessControlTests.setUpClass()
    case=AccessControlTests('test_anonymous_and_parent_object_scope_and_exports')
    case.setUp()
    lock=threading.Lock()
    def db():
        # Browser makes parallel reads; serialize sessions sharing the rollback connection.
        with lock:
            with case.factory() as session:yield session
    app.dependency_overrides[session_dependency]=db
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,lifespan='off',log_level='critical',access_log=False))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    try:
        for _ in range(100):
            if server.started:break
            time.sleep(.05)
        if not server.started:raise RuntimeError('Isolated HTTP server did not start.')
        config={'base':f'http://127.0.0.1:{port}','users':{k:v[1] for k,v in case.users.items()},'vehicles':case.vehicles,'students':case.students,'trips':case.trips}
        result=subprocess.run(['node','scripts/verify-auth.cjs'],cwd=Path('../frontend'),env={**os.environ,
            'SAFERIDE_AUTH_BROWSER_FIXTURE':json.dumps(config),'SAFERIDE_AUTH_BROWSER_PASSWORD':case.password},timeout=120)
        if result.returncode:raise RuntimeError('Browser checks failed (credentials suppressed).')
    finally:
        server.should_exit=True;thread.join(timeout=15)
        if thread.is_alive():raise RuntimeError('Isolated server did not stop.')
        case.tearDown()
    print('Browser fixture accounts/trips/positions rolled back; no operational records retained.')


if __name__=='__main__':main()
