import uvicorn

import config
from api.main import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run("run_api:app", host=config.API_HOST, port=config.API_PORT, reload=True)
