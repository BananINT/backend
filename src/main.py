from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.security import OAuth2PasswordBearer

app = FastAPI(root_path="/api")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


@app.get("/")
def root(nom:str):
    return {"message": "Hello world !", "nom": "Bonjour " + nom}

@app.get("/data")
async def data():
    return [{"id": i, "name": "Cours" + str(i)} for i in range(50)]

@app.post("/token")
async def login():
    # normally you'd validate username/password here
    return {"access_token": "example", "token_type": "bearer"}

@app.get("/items/")
async def read_items(token: Annotated[str, Depends(oauth2_scheme)]):
    return {"token": token}