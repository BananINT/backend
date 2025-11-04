from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import time
import secrets
import json

app = FastAPI(root_path="/api", title="Banana Clicker API")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage (replace with Redis/Database in production)
game_sessions = {}
leaderboard_data = []

# Pydantic models
class GameState(BaseModel):
    sessionId: str
    bananas: int
    bananasPerClick: int
    totalClicks: int
    lastClickTime: float

class LeaderboardEntry(BaseModel):
    name: str
    score: int
    date: str

class InitRequest(BaseModel):
    sessionId: Optional[str] = None

class InitResponse(BaseModel):
    sessionId: str
    gameState: GameState
    leaderboard: List[LeaderboardEntry]
    playerName: str

class ClickRequest(BaseModel):
    sessionId: str

class ClickResponse(BaseModel):
    success: bool
    newBananas: int
    message: Optional[str] = None

class UpgradeRequest(BaseModel):
    sessionId: str
    cost: int
    multiplier: int

class UpgradeResponse(BaseModel):
    success: bool
    newBananas: int
    newBananasPerClick: int
    message: Optional[str] = None

class SubmitScoreRequest(BaseModel):
    sessionId: str
    name: str
    score: int

class SubmitScoreResponse(BaseModel):
    success: bool
    leaderboard: List[LeaderboardEntry]

class ResetRequest(BaseModel):
    sessionId: str

class ResetResponse(BaseModel):
    success: bool
    gameState: GameState

# Helper functions
def generate_session_id() -> str:
    return f"session-{int(time.time())}-{secrets.token_hex(8)}"

def create_initial_state(session_id: str) -> GameState:
    return GameState(
        sessionId=session_id,
        bananas=0,
        bananasPerClick=1,
        totalClicks=0,
        lastClickTime=0
    )

def get_or_create_session(session_id: Optional[str]) -> tuple[str, GameState]:
    if session_id and session_id in game_sessions:
        return session_id, game_sessions[session_id]
    
    new_session_id = generate_session_id()
    initial_state = create_initial_state(new_session_id)
    game_sessions[new_session_id] = initial_state
    return new_session_id, initial_state

# API Endpoints
@app.post("/game/init", response_model=InitResponse)
async def init_game(request: InitRequest):
    """Initialize or restore a game session"""
    session_id, game_state = get_or_create_session(request.sessionId)
    
    return InitResponse(
        sessionId=session_id,
        gameState=game_state,
        leaderboard=sorted(leaderboard_data, key=lambda x: x.score, reverse=True)[:10],
        playerName=""  # Player name stored client-side
    )

@app.post("/game/click", response_model=ClickResponse)
async def handle_click(request: ClickRequest):
    """Validate and process a click"""
    if request.sessionId not in game_sessions:
        return ClickResponse(
            success=False,
            newBananas=0,
            message="Invalid session"
        )
    
    game_state = game_sessions[request.sessionId]
    current_time = time.time() * 1000  # Convert to milliseconds
    
    # Anti-cheat: max 20 clicks per second
    if current_time - game_state.lastClickTime < 50:
        return ClickResponse(
            success=False,
            newBananas=game_state.bananas,
            message="Too fast!"
        )
    
    # Update game state
    game_state.bananas += game_state.bananasPerClick
    game_state.totalClicks += 1
    game_state.lastClickTime = current_time
    
    return ClickResponse(
        success=True,
        newBananas=game_state.bananas
    )

@app.post("/game/upgrade", response_model=UpgradeResponse)
async def buy_upgrade(request: UpgradeRequest):
    """Validate and process an upgrade purchase"""
    if request.sessionId not in game_sessions:
        return UpgradeResponse(
            success=False,
            newBananas=0,
            newBananasPerClick=1,
            message="Invalid session"
        )
    
    game_state = game_sessions[request.sessionId]
    
    if game_state.bananas < request.cost:
        return UpgradeResponse(
            success=False,
            newBananas=game_state.bananas,
            newBananasPerClick=game_state.bananasPerClick,
            message="Not enough bananas"
        )
    
    # Process upgrade
    game_state.bananas -= request.cost
    game_state.bananasPerClick += request.multiplier
    
    return UpgradeResponse(
        success=True,
        newBananas=game_state.bananas,
        newBananasPerClick=game_state.bananasPerClick
    )

@app.post("/game/submit-score", response_model=SubmitScoreResponse)
async def submit_score(request: SubmitScoreRequest):
    """Submit a score to the leaderboard"""
    if not request.name.strip():
        return SubmitScoreResponse(success=False, leaderboard=[])
    
    # Add new entry
    new_entry = LeaderboardEntry(
        name=request.name.strip(),
        score=request.score,
        date=datetime.utcnow().isoformat()
    )
    
    leaderboard_data.append(new_entry)
    
    # Sort and keep top 10
    sorted_leaderboard = sorted(leaderboard_data, key=lambda x: x.score, reverse=True)[:10]
    
    # Update global leaderboard
    leaderboard_data.clear()
    leaderboard_data.extend(sorted_leaderboard)
    
    return SubmitScoreResponse(
        success=True,
        leaderboard=sorted_leaderboard
    )

@app.post("/game/reset", response_model=ResetResponse)
async def reset_game(request: ResetRequest):
    """Reset a game session"""
    if request.sessionId not in game_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    initial_state = create_initial_state(request.sessionId)
    game_sessions[request.sessionId] = initial_state
    
    return ResetResponse(
        success=True,
        gameState=initial_state
    )

@app.get("/game/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard():
    """Get the current leaderboard"""
    return sorted(leaderboard_data, key=lambda x: x.score, reverse=True)[:10]

@app.get("/")
async def root():
    return {"message": "Banana Clicker API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "sessions": len(game_sessions)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)