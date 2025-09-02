from fastapi import FastAPI

from app.routers import items, stores

app = FastAPI(title="Grocery API")

app.include_router(items.router, prefix="/items", tags=["items"])
app.include_router(stores.router, prefix="/stores", tags=["stores"])


@app.get("/")
def root():
    return {"message": "Welcome to Grocery Saver API"}
