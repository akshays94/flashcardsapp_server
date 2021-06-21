from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import user
from app.routers import deck


app = FastAPI()
app.include_router(user.router)
app.include_router(deck.router)

origins = [
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get('/')
def read_root():
    return 'Welcome to Flash Cards App API xxx'


# python3 -m venv flashcardsapp-venv
# source flashcardsapp-venv/bin/activate
# deactivate
# python3 -m pip install -r requirements/base.txt
# uvicorn main:app --reload --port 8002
