import uvicorn
from viepn.api import app
from viepn.config import load_settings

if __name__ == '__main__':
    cfg = load_settings()
    print('\nViePN iOS Manager is running')
    print(f'Dashboard: http://127.0.0.1:{cfg.port}')
    print(f'Access token file: {cfg.root / "access_token.txt"}')
    if cfg.host != '127.0.0.1':
        print('LAN mode enabled; protect this server and do not expose it to the public Internet.')
    uvicorn.run(app, host=cfg.host, port=cfg.port, log_level='info')
