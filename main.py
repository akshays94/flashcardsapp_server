from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import user
from app.routers import deck


app = FastAPI()
app.include_router(user.router)
app.include_router(deck.router)

origins = [
    "http://localhost:8080",
    "https://flashlearnapp.netlify.app",
    "https://flashcardsapp-client.vercel.app"
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
    return 'Welcome to Flash Cards App API'
