from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from game import router as game_router
from enhanced_game import router as enhanced_game_router

app = FastAPI(root_path="/api",title="Banana Clicker API")

# Allow everything for testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register both apps
app.include_router(game_router, prefix="/game")
app.include_router(enhanced_game_router, prefix="/enhanced-game")

@app.get("/")
async def root():
    return {"message": "Banana Clicker API root"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
