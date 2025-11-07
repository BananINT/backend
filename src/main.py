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
    playerName: Optional[str] = ""  # Track player name with session

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
    sessionId: str  # Track which session this score belongs to

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
    leaderboard: List[LeaderboardEntry]  # Return updated leaderboard on each sync
    message: Optional[str] = None

class UpgradeRequest(BaseModel):
    sessionId: str
    upgradeId: str

class UpgradeResponse(BaseModel):
    success: bool
    gameState: GameState
    upgrades: List[UpgradeType]
    leaderboard: List[LeaderboardEntry]  # Return updated leaderboard
    message: Optional[str] = None

class SubmitScoreRequest(BaseModel):
    sessionId: str
    name: str

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
        print(f"💾 Data saved: {len(game_sessions)} sessions, {len(leaderboard_data)} leaderboard entries")
    except Exception as e:
        print(f"❌ Error saving data: {e}")

def load_data():
    """Load game data from disk and reload fresh data"""
    global game_sessions, upgrades_data, leaderboard_data
    
    if not os.path.exists(SAVE_FILE):
        print("📂 No save file found, starting fresh")
        return
    
    try:
        with open(SAVE_FILE, "r") as f:
            data = json.load(f)
        
        # Clear existing data
        game_sessions.clear()
        upgrades_data.clear()
        leaderboard_data.clear()
        
        # Restore objects
        for sid, gs in data.get("game_sessions", {}).items():
            game_sessions[sid] = GameState(**gs)
        for sid, ups in data.get("upgrades_data", {}).items():
            upgrades_data[sid] = {uid: UpgradeType(**up) for uid, up in ups.items()}
        for lb in data.get("leaderboard_data", []):
            leaderboard_data.append(LeaderboardEntry(**lb))
        
        print(f"✅ Loaded {len(game_sessions)} sessions, {len(leaderboard_data)} leaderboard entries")
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        # Don't crash, just start fresh
        game_sessions.clear()
        upgrades_data.clear()
        leaderboard_data.clear()

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
        lastSyncTime=time.time() * 1000,
        playerName=""
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

def calculate_total_spent_on_upgrades(upgrades: Dict[str, UpgradeType]) -> int:
    """Calculate how many bananas were spent buying all current upgrades"""
    total_spent = 0
    for upgrade in upgrades.values():
        if upgrade.owned > 0:
            for n in range(upgrade.owned):
                cost = math.floor(upgrade.baseCost * math.pow(1.15, n))
                total_spent += cost
    return total_spent

def calculate_maximum_possible_bananas(game_state: GameState, upgrades: Dict[str, UpgradeType]) -> int:
    """
    Calculate the MAXIMUM theoretically possible bananas this session could have earned.
    This is used to cap submitted scores if they exceed realistic values.
    """
    # Maximum from all clicks ever made
    max_from_clicks = game_state.totalClicks * game_state.bananasPerClick
    
    # Maximum from time-based generation (since session creation)
    current_time = time.time() * 1000
    session_age_seconds = (current_time - game_state.lastSyncTime) / 1000
    max_offline_seconds = 8 * 60 * 60  # 8 hours max
    time_for_generation = min(session_age_seconds, max_offline_seconds)
    max_from_time = game_state.bananasPerSecond * time_for_generation
    
    # Calculate spending
    total_spent = calculate_total_spent_on_upgrades(upgrades)
    
    # Maximum possible = earnings - spending
    max_possible = int(max_from_clicks + max_from_time - total_spent)
    
    return max(0, max_possible)  # Can't be negative

def update_leaderboard(session_id: str, player_name: str, score: int) -> List[LeaderboardEntry]:
    """
    Update or add a player's score to the leaderboard.
    If the session already has an entry, update it. Otherwise, create new.
    Returns the updated top 10 leaderboard.
    """
    # Reload data from disk to get latest state
    load_data()
    
    # Find existing entry for this session
    existing_entry = None
    for entry in leaderboard_data:
        if entry.sessionId == session_id:
            existing_entry = entry
            break
    
    if existing_entry:
        # Update existing entry only if score is higher
        if score > existing_entry.score:
            print(f"📈 Updating score for {player_name}: {existing_entry.score} → {score}")
            existing_entry.score = score
            existing_entry.name = player_name
            existing_entry.date = datetime.utcnow().isoformat()
        else:
            print(f"⏸️  Score {score} not higher than existing {existing_entry.score}, keeping old score")
    else:
        # Create new entry
        print(f"🆕 New leaderboard entry: {player_name} with {score} bananas")
        new_entry = LeaderboardEntry(
            name=player_name[:20],
            score=score,
            date=datetime.utcnow().isoformat(),
            sessionId=session_id
        )
        leaderboard_data.append(new_entry)
    
    # Sort and keep top 10
    sorted_leaderboard = sorted(leaderboard_data, key=lambda x: x.score, reverse=True)[:10]
    
    # Update global leaderboard
    leaderboard_data.clear()
    leaderboard_data.extend(sorted_leaderboard)
    
    save_data()
    
    return sorted_leaderboard

def get_leaderboard() -> List[LeaderboardEntry]:
    """Get current top 10 leaderboard"""
    return sorted(leaderboard_data, key=lambda x: x.score, reverse=True)[:10]

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
        leaderboard=get_leaderboard(),
        playerName=game_state.playerName or ""
    )

@app.post("/game/sync", response_model=SyncResponse)
async def sync_game(request: SyncRequest):
    """
    Sync game state with server.
    Now automatically updates leaderboard if player has a name set.
    """
    if request.sessionId not in game_sessions:
        print(f"❌ Invalid session ID: {request.sessionId}")
        return SyncResponse(
            success=False,
            gameState=create_initial_state(request.sessionId),
            leaderboard=get_leaderboard(),
            message="Invalid session - please refresh the page"
        )
    
    game_state = game_sessions[request.sessionId]
    upgrades = upgrades_data[request.sessionId]
    current_time = time.time() * 1000
    
    # ANTI-CHEAT: Validate clicks are reasonable (max 20/sec)
    time_since_last_sync = (current_time - game_state.lastSyncTime) / 1000
    max_possible_clicks = math.ceil(time_since_last_sync * 20)
    
    actual_clicks = request.pendingClicks
    if request.pendingClicks > max_possible_clicks:
        print(f"⚠️ Suspicious click rate from {request.sessionId}:")
        print(f"   Reported: {request.pendingClicks} clicks in {time_since_last_sync:.2f}s")
        print(f"   Maximum possible: {max_possible_clicks} clicks")
        print(f"   Capping to maximum...")
        actual_clicks = max_possible_clicks
    
    # Calculate time-based earnings
    time_earnings = calculate_time_based_earnings(game_state, upgrades, current_time)
    
    # Calculate click earnings (server-side calculation)
    click_earnings = actual_clicks * game_state.bananasPerClick
    
    # Update game state
    game_state.bananas += time_earnings + click_earnings
    game_state.totalClicks += actual_clicks
    game_state.lastSyncTime = current_time
    
    # Recalculate stats (server is authority)
    game_state.bananasPerClick = calculate_bananas_per_click(upgrades)
    game_state.bananasPerSecond = calculate_bananas_per_second(upgrades)
    
    # AUTO-UPDATE LEADERBOARD: If player has a name, update their score
    updated_leaderboard = get_leaderboard()
    if game_state.playerName and game_state.playerName.strip():
        current_score = int(game_state.bananas)
        if current_score > 0:
            updated_leaderboard = update_leaderboard(
                request.sessionId,
                game_state.playerName,
                current_score
            )
    
    save_data()
    
    return SyncResponse(
        success=True,
        gameState=game_state,
        leaderboard=updated_leaderboard
    )

@app.post("/game/upgrade", response_model=UpgradeResponse)
async def buy_upgrade(request: UpgradeRequest):
    """Purchase an upgrade - fully server-side validated"""
    if request.sessionId not in game_sessions:
        print(f"❌ Invalid session ID for upgrade: {request.sessionId}")
        return UpgradeResponse(
            success=False,
            gameState=create_initial_state(request.sessionId),
            upgrades=[],
            leaderboard=get_leaderboard(),
            message="Invalid session"
        )
    
    game_state = game_sessions[request.sessionId]
    upgrades = upgrades_data[request.sessionId]
    
    if request.upgradeId not in upgrades:
        print(f"❌ Invalid upgrade ID: {request.upgradeId}")
        return UpgradeResponse(
            success=False,
            gameState=game_state,
            upgrades=list(upgrades.values()),
            leaderboard=get_leaderboard(),
            message="Invalid upgrade"
        )
    
    upgrade = upgrades[request.upgradeId]
    cost = calculate_upgrade_cost(upgrade)
    
    if game_state.bananas < cost:
        print(f"⚠️ Insufficient funds for {request.sessionId}:")
        print(f"   Upgrade: {upgrade.name} (#{upgrade.owned + 1})")
        print(f"   Cost: {cost}, Has: {int(game_state.bananas)}")
        return UpgradeResponse(
            success=False,
            gameState=game_state,
            upgrades=list(upgrades.values()),
            leaderboard=get_leaderboard(),
            message=f"Not enough bananas. Need {cost}, have {int(game_state.bananas)}"
        )
    
    # Process upgrade
    game_state.bananas -= cost
    upgrade.owned += 1
    
    # Recalculate stats
    game_state.bananasPerClick = calculate_bananas_per_click(upgrades)
    game_state.bananasPerSecond = calculate_bananas_per_second(upgrades)
    
    print(f"✅ Upgrade purchased: {upgrade.name} (#{upgrade.owned}) by {request.sessionId}")
    print(f"   New stats: {game_state.bananasPerClick} per click, {game_state.bananasPerSecond:.1f} per second")
    
    # Auto-update leaderboard if player has name
    updated_leaderboard = get_leaderboard()
    if game_state.playerName and game_state.playerName.strip():
        current_score = int(game_state.bananas)
        updated_leaderboard = update_leaderboard(
            request.sessionId,
            game_state.playerName,
            current_score
        )
    
    save_data()
    
    return UpgradeResponse(
        success=True,
        gameState=game_state,
        upgrades=list(upgrades.values()),
        leaderboard=updated_leaderboard
    )

@app.post("/game/submit-score", response_model=SubmitScoreResponse)
async def submit_score(request: SubmitScoreRequest):
    """
    Submit or update player name for leaderboard.
    The score is determined from the server-side game state (game_state.bananas),
    ignoring any client-submitted score.
    If bananas exceed the maximum possible, they're capped to that value.
    """
    trimmed_name = request.name.strip()
    if not trimmed_name:
        print(f"❌ Empty name submitted from {request.sessionId}")
        return SubmitScoreResponse(
            success=False,
            leaderboard=get_leaderboard(),
            message="Player name cannot be empty"
        )

    # Verify session exists
    if request.sessionId not in game_sessions:
        print(f"❌ Invalid session ID for score submission: {request.sessionId}")
        return SubmitScoreResponse(
            success=False,
            leaderboard=get_leaderboard(),
            message="Invalid session - please refresh the page"
        )

    # Reload latest data
    load_data()

    game_state = game_sessions[request.sessionId]
    upgrades = upgrades_data[request.sessionId]

    # Calculate maximum possible score for this session
    max_possible_score = calculate_maximum_possible_bananas(game_state, upgrades)
    server_score = int(game_state.bananas)

    # Cap score if it exceeds theoretical maximum
    if server_score > max_possible_score:
        print(f"⚠️ Score exceeds maximum possible for {request.sessionId}:")
        print(f"   Server bananas: {server_score}")
        print(f"   Maximum possible: {max_possible_score}")
        print(f"   Total clicks: {game_state.totalClicks}")
        print(f"   Per click: {game_state.bananasPerClick}")
        print(f"   Per second: {game_state.bananasPerSecond}")
        print(f"   Using maximum possible value instead")

        final_score = max_possible_score
        message = f"Score capped to maximum possible: {final_score:,} bananas"
    else:
        final_score = server_score
        message = f"Score submitted: {final_score:,} bananas"

    # Update player name in session
    game_state.playerName = trimmed_name

    # Update leaderboard
    print(f"✅ Updating leaderboard for {trimmed_name}: {final_score} bananas")
    updated_leaderboard = update_leaderboard(request.sessionId, trimmed_name, final_score)

    return SubmitScoreResponse(
        success=True,
        leaderboard=updated_leaderboard,
        message=message
    )

@app.post("/game/reset", response_model=ResetResponse)
async def reset_game(request: ResetRequest):
    """Reset a game session"""
    if request.sessionId not in game_sessions:
        print(f"❌ Invalid session ID for reset: {request.sessionId}")
        raise HTTPException(status_code=404, detail="Session not found")
    
    initial_state = create_initial_state(request.sessionId)
    initial_upgrades = create_default_upgrades(request.sessionId)
    
    game_sessions[request.sessionId] = initial_state
    upgrades_data[request.sessionId] = initial_upgrades
    
    print(f"🔄 Game reset for session {request.sessionId}")
    
    save_data()
    return ResetResponse(
        success=True,
        gameState=initial_state,
        upgrades=list(initial_upgrades.values())
    )

@app.get("/game/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard_endpoint():
    """Get the current leaderboard"""
    return get_leaderboard()

@app.get("/")
async def root():
    return {"message": "Banana Clicker API - Auto-Updating Leaderboard"}

@app.get("/health")
async def health_check():
    total_bananas = sum(gs.bananas for gs in game_sessions.values())
    return {
        "status": "healthy",
        "sessions": len(game_sessions),
        "leaderboard_entries": len(leaderboard_data),
        "total_bananas_farmed": int(total_bananas)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)