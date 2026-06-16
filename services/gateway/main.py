from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title='juridico-platform-gateway', version='0.1.0')


@app.get('/health')
def health():
    return {'status': 'healthy', 'service': 'gateway'}


@app.get('/')
def root():
    return JSONResponse({'name': 'juridico-platform-gateway', 'version': '0.1.0'})
