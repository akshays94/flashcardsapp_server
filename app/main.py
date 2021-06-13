from fastapi import FastAPI
from routers import user
from routers import bundle


app = FastAPI()
app.include_router(user.router)
app.include_router(bundle.router)


@app.get('/')
def read_root():
    return 'Welcome to Flash Cards App API'


# python3 -m venv flashcardsapp-venv
# source flashcardsapp-venv/bin/activate
# deactivate
# python3 -m pip install -r requirements/base.txt
# uvicorn main:app --reload --port 8002
