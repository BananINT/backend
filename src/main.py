from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime
import time
import secrets
import math
import json
import os

app = FastAPI(root_path="/api", title="Banana Clicker API - Optimized")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage
game_sessions: Dict[str, 'GameState'] = {}
upgrades_data: Dict[str, Dict[str, 'UpgradeType']] = {}
leaderboard_data: List['LeaderboardEntry'] = []

# Pydantic models
class GameState(BaseModel):
    sessionId: str
    bananas: float
    bananasPerClick: int
    bananasPerSecond: float
    totalClicks: int
    lastSyncTime: float

class UpgradeType(BaseModel):
    id: str
    name: str
    baseCost: int
    multiplier: int
    type: str  # 'click' or 'auto'
    owned: int

class LeaderboardEntry(BaseModel):
    name: str
    score: int
    date: str

class InitRequest(BaseModel):
    sessionId: Optional[str] = None

class InitResponse(BaseModel):
    sessionId: str
    gameState: GameState
    upgrades: List[UpgradeType]
    leaderboard: List[LeaderboardEntry]
    playerName: str

class SyncRequest(BaseModel):
    sessionId: str
    pendingClicks: int
    clientBananas: float
    lastSyncTime: float

class SyncResponse(BaseModel):
    success: bool
    gameState: GameState
    message: Optional[str] = None

class UpgradeRequest(BaseModel):
    sessionId: str
    upgradeId: str

class UpgradeResponse(BaseModel):
    success: bool
    gameState: GameState
    upgrades: List[UpgradeType]
    message: Optional[str] = None

class SubmitScoreRequest(BaseModel):
    sessionId: str
    name: str
    score: int

class SubmitScoreResponse(BaseModel):
    success: bool
    leaderboard: List[LeaderboardEntry]
    message: Optional[str] = None

class ResetRequest(BaseModel):
    sessionId: str

class ResetResponse(BaseModel):
    success: bool
    gameState: GameState
    upgrades: List[UpgradeType]

# Default upgrades configuration
DEFAULT_UPGRADES = [
    {
        "id": "click_1",
        "name": "Better Fingers",
        "baseCost": 10,
        "multiplier": 1,
        "type": "click",
        "owned": 0
    },
    {
        "id": "click_2",
        "name": "Stronger Arms",
        "baseCost": 100,
        "multiplier": 5,
        "type": "click",
        "owned": 0
    },
    {
        "id": "click_3",
        "name": "Banana Peeler",
        "baseCost": 1000,
        "multiplier": 10,
        "type": "click",
        "owned": 0
    },
    {
        "id": "auto_1",
        "name": "Banana Tree",
        "baseCost": 50,
        "multiplier": 1,
        "type": "auto",
        "owned": 0
    },
    {
        "id": "auto_2",
        "name": "Banana Harvester Bot",
        "baseCost": 500,
        "multiplier": 5,
        "type": "auto",
        "owned": 0
    },
    {
        "id": "auto_3",
        "name": "Banana Plantation",
        "baseCost": 5000,
        "multiplier": 20,
        "type": "auto",
        "owned": 0
    },
    {
        "id": "auto_4",
        "name": "Banana Factory",
        "baseCost": 50000,
        "multiplier": 60,
        "type": "auto",
        "owned": 0
    },
    {
        "id": "auto_5",
        "name": "Banana Enrichment Center",
        "baseCost": 500000,
        "multiplier": 120,
        "type": "auto",
        "owned": 0
    }
]

SAVE_FILE = "/app/data/bananint_data.json"

def save_data():
    """Save all game data to disk"""
    try:
        os.makedirs(os.path.dirname(SAVE_FILE), exist_ok=True)
        data = {
            "game_sessions": {sid: gs.dict() for sid, gs in game_sessions.items()},
            "upgrades_data": {
                sid: {uid: up.dict() for uid, up in upgrades.items()}
                for sid, upgrades in upgrades_data.items()
            },
            "leaderboard_data": [lb.dict() for lb in leaderboard_data],
        }
        with open(SAVE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving data: {e}")

def load_data():
    """Load game data from disk"""
    if not os.path.exists(SAVE_FILE):
        return
    try:
        with open(SAVE_FILE, "r") as f:
            data = json.load(f)
        # Restore objects
        for sid, gs in data.get("game_sessions", {}).items():
            game_sessions[sid] = GameState(**gs)
        for sid, ups in data.get("upgrades_data", {}).items():
            upgrades_data[sid] = {uid: UpgradeType(**up) for uid, up in ups.items()}
        for lb in data.get("leaderboard_data", []):
            leaderboard_data.append(LeaderboardEntry(**lb))
        print(f"Loaded {len(game_sessions)} sessions, {len(leaderboard_data)} leaderboard entries")
    except Exception as e:
        print(f"Error loading data: {e}")

load_data()

# Helper functions
def generate_session_id() -> str:
    return f"session-{int(time.time())}-{secrets.token_hex(8)}"

def create_initial_state(session_id: str) -> GameState:
    return GameState(
        sessionId=session_id,
        bananas=0,
        bananasPerClick=1,
        bananasPerSecond=0,
        totalClicks=0,
        lastSyncTime=time.time() * 1000
    )

def create_default_upgrades(session_id: str) -> Dict[str, UpgradeType]:
    upgrades = {}
    for upgrade_data in DEFAULT_UPGRADES:
        upgrade = UpgradeType(**upgrade_data)
        upgrades[upgrade.id] = upgrade
    return upgrades

def calculate_upgrade_cost(upgrade: UpgradeType) -> int:
    """Cost increases by 15% per owned upgrade"""
    return math.floor(upgrade.baseCost * math.pow(1.15, upgrade.owned))

def calculate_bananas_per_second(upgrades: Dict[str, UpgradeType]) -> float:
    """Calculate total bananas per second from auto-generators"""
    total = 0.0
    for upgrade in upgrades.values():
        if upgrade.type == "auto" and upgrade.owned > 0:
            total += upgrade.multiplier * upgrade.owned
    return total

def calculate_bananas_per_click(upgrades: Dict[str, UpgradeType]) -> int:
    """Calculate total bananas per click from click upgrades"""
    total = 1  # Base click power
    for upgrade in upgrades.values():
        if upgrade.type == "click" and upgrade.owned > 0:
            total += upgrade.multiplier * upgrade.owned
    return total

def calculate_time_based_earnings(
    game_state: GameState,
    upgrades: Dict[str, UpgradeType],
    current_time_ms: float
) -> float:
    """Calculate bananas earned from auto-generation since last sync"""
    if game_state.bananasPerSecond <= 0:
        return 0
    
    time_diff_seconds = (current_time_ms - game_state.lastSyncTime) / 1000
    
    # Cap to 8 hours of offline time
    max_offline_seconds = 8 * 60 * 60
    time_diff_seconds = min(time_diff_seconds, max_offline_seconds)
    
    return game_state.bananasPerSecond * time_diff_seconds

def calculate_expected_bananas(game_state: GameState, upgrades: Dict[str, UpgradeType]) -> float:
    """
    Calculate what the player's banana count SHOULD be based on:
    - Their previous synced bananas
    - Time-based earnings since last sync
    This is used to verify submitted scores aren't cheated
    """
    current_time = time.time() * 1000
    time_earnings = calculate_time_based_earnings(game_state, upgrades, current_time)
    expected = game_state.bananas + time_earnings
    return expected

def get_or_create_session(session_id: Optional[str]) -> tuple[str, GameState, Dict[str, UpgradeType]]:
    if session_id and session_id in game_sessions:
        return session_id, game_sessions[session_id], upgrades_data[session_id]
    
    new_session_id = generate_session_id()
    initial_state = create_initial_state(new_session_id)
    initial_upgrades = create_default_upgrades(new_session_id)
    
    game_sessions[new_session_id] = initial_state
    upgrades_data[new_session_id] = initial_upgrades
    
    return new_session_id, initial_state, initial_upgrades

# API Endpoints
@app.post("/game/init", response_model=InitResponse)
async def init_game(request: InitRequest):
    """Initialize or restore a game session"""
    session_id, game_state, upgrades = get_or_create_session(request.sessionId)
    
    # Calculate any time-based earnings
    current_time = time.time() * 1000
    time_earnings = calculate_time_based_earnings(game_state, upgrades, current_time)
    
    if time_earnings > 0:
        game_state.bananas += time_earnings
        game_state.lastSyncTime = current_time
    
    return InitResponse(
        sessionId=session_id,
        gameState=game_state,
        upgrades=list(upgrades.values()),
        leaderboard=sorted(leaderboard_data, key=lambda x: x.score, reverse=True)[:10],
        playerName=""
    )

@app.post("/game/sync", response_model=SyncResponse)
async def sync_game(request: SyncRequest):
    """
    Sync game state with server
    Handles batched clicks and time-based auto-generation
    """
    if request.sessionId not in game_sessions:
        return SyncResponse(
            success=False,
            gameState=create_initial_state(request.sessionId),
            message="Invalid session"
        )
    
    game_state = game_sessions[request.sessionId]
    upgrades = upgrades_data[request.sessionId]
    current_time = time.time() * 1000
    
    # Calculate time-based earnings
    time_earnings = calculate_time_based_earnings(game_state, upgrades, current_time)
    
    # Calculate click earnings
    click_earnings = request.pendingClicks * game_state.bananasPerClick
    
    # Update game state
    game_state.bananas += time_earnings + click_earnings
    game_state.totalClicks += request.pendingClicks
    game_state.lastSyncTime = current_time
    
    # Recalculate bananasPerSecond in case it changed
    game_state.bananasPerSecond = calculate_bananas_per_second(upgrades)
    
    # Save after every sync
    save_data()
    
    return SyncResponse(
        success=True,
        gameState=game_state
    )

@app.post("/game/upgrade", response_model=UpgradeResponse)
async def buy_upgrade(request: UpgradeRequest):
    """Purchase an upgrade"""
    if request.sessionId not in game_sessions:
        return UpgradeResponse(
            success=False,
            gameState=create_initial_state(request.sessionId),
            upgrades=[],
            message="Invalid session"
        )
    
    game_state = game_sessions[request.sessionId]
    upgrades = upgrades_data[request.sessionId]
    
    if request.upgradeId not in upgrades:
        return UpgradeResponse(
            success=False,
            gameState=game_state,
            upgrades=list(upgrades.values()),
            message="Invalid upgrade"
        )
    
    upgrade = upgrades[request.upgradeId]
    cost = calculate_upgrade_cost(upgrade)
    
    if game_state.bananas < cost:
        return UpgradeResponse(
            success=False,
            gameState=game_state,
            upgrades=list(upgrades.values()),
            message="Not enough bananas"
        )
    
    # Process upgrade
    game_state.bananas -= cost
    upgrade.owned += 1
    
    # Recalculate stats
    game_state.bananasPerClick = calculate_bananas_per_click(upgrades)
    game_state.bananasPerSecond = calculate_bananas_per_second(upgrades)
    
    save_data()
    return UpgradeResponse(
        success=True,
        gameState=game_state,
        upgrades=list(upgrades.values())
    )

@app.post("/game/submit-score", response_model=SubmitScoreResponse)
async def submit_score(request: SubmitScoreRequest):
    """
    Submit a score to the leaderboard with server-side verification
    """
    if not request.name.strip():
        return SubmitScoreResponse(
            success=False, 
            leaderboard=[],
            message="Name cannot be empty"
        )
    
    # Verify session exists
    if request.sessionId not in game_sessions:
        return SubmitScoreResponse(
            success=False,
            leaderboard=sorted(leaderboard_data, key=lambda x: x.score, reverse=True)[:10],
            message="Invalid session"
        )
    
    game_state = game_sessions[request.sessionId]
    upgrades = upgrades_data[request.sessionId]
    
    # Calculate what the score SHOULD be based on server state
    expected_score = calculate_expected_bananas(game_state, upgrades)
    submitted_score = request.score
    
    # Allow some tolerance for client-side rounding and timing differences (5% tolerance)
    tolerance = expected_score * 0.05
    score_difference = abs(submitted_score - expected_score)
    
    if score_difference > tolerance:
        # Score doesn't match server state - possible cheating
        print(f"⚠️ Score verification failed for session {request.sessionId}")
        print(f"   Expected: {expected_score:.2f}, Submitted: {submitted_score}, Diff: {score_difference:.2f}")
        
        return SubmitScoreResponse(
            success=False,
            leaderboard=sorted(leaderboard_data, key=lambda x: x.score, reverse=True)[:10],
            message=f"Score verification failed. Expected around {int(expected_score)}, got {submitted_score}"
        )
    
    # Score is valid - use server's authoritative value
    verified_score = int(expected_score)
    
    print(f"✅ Score verified for {request.name}: {verified_score} bananas")
    
    # Add new entry with verified score
    new_entry = LeaderboardEntry(
        name=request.name.strip()[:20],  # Limit name length
        score=verified_score,
        date=datetime.utcnow().isoformat()
    )
    
    leaderboard_data.append(new_entry)
    
    # Sort and keep top 10
    sorted_leaderboard = sorted(leaderboard_data, key=lambda x: x.score, reverse=True)[:10]
    
    # Update global leaderboard
    leaderboard_data.clear()
    leaderboard_data.extend(sorted_leaderboard)
    
    save_data()
    
    return SubmitScoreResponse(
        success=True,
        leaderboard=sorted_leaderboard,
        message=f"Score verified: {verified_score} bananas"
    )

@app.post("/game/reset", response_model=ResetResponse)
async def reset_game(request: ResetRequest):
    """Reset a game session"""
    if request.sessionId not in game_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    initial_state = create_initial_state(request.sessionId)
    initial_upgrades = create_default_upgrades(request.sessionId)
    
    game_sessions[request.sessionId] = initial_state
    upgrades_data[request.sessionId] = initial_upgrades
    
    save_data()
    return ResetResponse(
        success=True,
        gameState=initial_state,
        upgrades=list(initial_upgrades.values())
    )

@app.get("/game/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard():
    """Get the current leaderboard"""
    return sorted(leaderboard_data, key=lambda x: x.score, reverse=True)[:10]

@app.get("/")
async def root():
    return {"message": "Banana Clicker API - Optimized Version with Score Verification"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "sessions": len(game_sessions),
        "leaderboard_entries": len(leaderboard_data),
        "total_bananas_farmed": sum(gs.bananas for gs in game_sessions.values())
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)