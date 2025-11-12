from fastapi import APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime
import time
import secrets
import math
import json
import os
import random

router = APIRouter()

# In-memory storage
game_sessions: Dict[str, 'GameState'] = {}
upgrades_data: Dict[str, Dict[str, 'UpgradeType']] = {}
leaderboard_data: List['LeaderboardEntry'] = []
achievements_data: Dict[str, Dict[str, 'Achievement']] = {}
active_events: Dict[str, 'ActiveEvent'] = {}

# Pydantic models
class GameState(BaseModel):
    sessionId: str
    bananas: float
    bananasPerClick: int
    bananasPerSecond: float
    totalClicks: int
    lastSyncTime: float
    playerName: Optional[str] = ""
    bananaDNA: int = 0  # Prestige currency
    totalBananasEarned: float = 0  # Lifetime earnings
    prestigeCount: int = 0
    selectedSkin: str = "default"
    ownedSkins: List[str] = ["default"]
    activeBoosts: List[Dict] = []  # Active temporary boosts
    lastEventCheck: float = 0

class UpgradeType(BaseModel):
    id: str
    name: str
    baseCost: int
    multiplier: int
    type: str  # 'click', 'auto', 'boost', 'prestige', 'synergy'
    owned: int
    description: Optional[str] = ""
    unlockRequirement: Optional[Dict] = None

class Achievement(BaseModel):
    id: str
    name: str
    description: str
    requirement: Dict  # {"type": "clicks", "value": 1000}
    reward: Dict  # {"type": "multiplier", "value": 0.01}
    unlocked: bool = False
    unlockedAt: Optional[str] = None

class ActiveEvent(BaseModel):
    id: str
    type: str  # 'rain', 'golden', 'festival'
    startTime: float
    duration: float  # seconds
    multiplier: Optional[float] = 1.0
    active: bool = True

class LeaderboardEntry(BaseModel):
    name: str
    score: int
    date: str
    sessionId: str
    prestigeCount: int = 0

class PublicLeaderboardEntry(BaseModel):
    name: str
    score: int
    date: str
    prestigeCount: int = 0

class InitRequest(BaseModel):
    sessionId: Optional[str] = None

class InitResponse(BaseModel):
    sessionId: str
    gameState: GameState
    upgrades: List[UpgradeType]
    leaderboard: List[PublicLeaderboardEntry]
    playerName: str
    achievements: List[Achievement]
    activeEvents: List[ActiveEvent]

class SyncRequest(BaseModel):
    sessionId: str
    pendingClicks: int
    clientBananas: float
    lastSyncTime: float

class SyncResponse(BaseModel):
    success: bool
    gameState: GameState
    leaderboard: List[PublicLeaderboardEntry]
    achievements: List[Achievement]
    activeEvents: List[ActiveEvent]
    message: Optional[str] = None

class UpgradeRequest(BaseModel):
    sessionId: str
    upgradeId: str

class UpgradeResponse(BaseModel):
    success: bool
    gameState: GameState
    upgrades: List[UpgradeType]
    leaderboard: List[PublicLeaderboardEntry]
    achievements: List[Achievement]
    message: Optional[str] = None

class PrestigeRequest(BaseModel):
    sessionId: str

class PrestigeResponse(BaseModel):
    success: bool
    gameState: GameState
    upgrades: List[UpgradeType]
    bananaDNAGained: int
    message: str

class SkinRequest(BaseModel):
    sessionId: str
    skinId: str

class EventClickRequest(BaseModel):
    sessionId: str
    eventId: str

# Enhanced upgrades configuration
DEFAULT_UPGRADES = [
    # Click upgrades
    {
        "id": "click_1",
        "name": "Better Fingers",
        "baseCost": 10,
        "multiplier": 1,
        "type": "click",
        "owned": 0,
        "description": "🖱️ +1 banana per click"
    },
    {
        "id": "click_2",
        "name": "Stronger Arms",
        "baseCost": 100,
        "multiplier": 5,
        "type": "click",
        "owned": 0,
        "description": "🖱️ +5 bananas per click"
    },
    {
        "id": "click_3",
        "name": "Banana Gloves",
        "baseCost": 1000,
        "multiplier": 10,
        "type": "click",
        "owned": 0,
        "description": "🖱️ +10 bananas per click"
    },
    {
        "id": "click_4",
        "name": "Banana Peeler",
        "baseCost": 10000,
        "multiplier": 25,
        "type": "click",
        "owned": 0,
        "description": "🖱️ +25 bananas per click"
    },
    {
        "id": "click_5",
        "name": "Golden Banana Touch",
        "baseCost": 100000,
        "multiplier": 100,
        "type": "click",
        "owned": 0,
        "description": "🖱️ +100 bananas per click"
    },
    
    # Auto upgrades
    {
        "id": "auto_1",
        "name": "Banana Tree",
        "baseCost": 50,
        "multiplier": 1,
        "type": "auto",
        "owned": 0,
        "description": "⚙️ +1 banana/sec"
    },
    {
        "id": "auto_2",
        "name": "Banana Harvester Bot",
        "baseCost": 500,
        "multiplier": 5,
        "type": "auto",
        "owned": 0,
        "description": "⚙️ +5 bananas/sec"
    },
    {
        "id": "auto_3",
        "name": "Banana Plantation",
        "baseCost": 5000,
        "multiplier": 20,
        "type": "auto",
        "owned": 0,
        "description": "⚙️ +20 bananas/sec"
    },
    {
        "id": "auto_4",
        "name": "Banana Factory",
        "baseCost": 50000,
        "multiplier": 60,
        "type": "auto",
        "owned": 0,
        "description": "⚙️ +60 bananas/sec"
    },
    {
        "id": "auto_5",
        "name": "Banana Enrichment Center",
        "baseCost": 500000,
        "multiplier": 120,
        "type": "auto",
        "owned": 0,
        "description": "⚙️ +120 bananas/sec"
    },
    {
        "id": "auto_6",
        "name": "Banana Shipping Fleet",
        "baseCost": 5000000,
        "multiplier": 500,
        "type": "auto",
        "owned": 0,
        "description": "⚙️ +500 bananas/sec"
    },
    {
        "id": "auto_7",
        "name": "Banana Space Program",
        "baseCost": 50000000,
        "multiplier": 2000,
        "type": "auto",
        "owned": 0,
        "description": "⚙️ +2000 bananas/sec"
    },
    {
        "id": "auto_8",
        "name": "Banana Multiverse Farm",
        "baseCost": 500000000,
        "multiplier": 10000,
        "type": "auto",
        "owned": 0,
        "description": "⚙️ +10000 bananas/sec"
    },
    
    # Synergy upgrades
    {
        "id": "synergy_1",
        "name": "Auto-clicker Bots",
        "baseCost": 1000000,
        "multiplier": 1,
        "type": "synergy",
        "owned": 0,
        "description": "⚡ Automatically clicks once every 10 second"
    },
    {
        "id": "synergy_2",
        "name": "Photosynthetic Bananas",
        "baseCost": 100000000,
        "multiplier": 1,
        "type": "synergy",
        "owned": 0,
        "description": "⚡ Auto upgrades boost click power by 10%"
    },
    
    # Prestige upgrades
    {
        "id": "prestige_1",
        "name": "Banana Deity Blessing",
        "baseCost": 10,
        "multiplier": 5,
        "type": "prestige",
        "owned": 0,
        "description": "x2 global multiplier (Cost: DNA)",
        "unlockRequirement": {"prestigeCount": 1}
    },
    {
        "id": "prestige_2",
        "name": "Quantum Peel Generator",
        "baseCost": 50,
        "multiplier": 2,
        "type": "prestige",
        "owned": 0,
        "description": "Doubles auto production (Cost: DNA)",
        "unlockRequirement": {"prestigeCount": 1}
    }
]

DEFAULT_ACHIEVEMENTS = [
    {
        "id": "ach_clicks_1",
        "name": "First Steps",
        "description": "Click 100 times",
        "requirement": {"type": "clicks", "value": 100},
        "reward": {"type": "multiplier", "value": 0.01}
    },
    {
        "id": "ach_clicks_2",
        "name": "Click Master",
        "description": "Click 1,000 times",
        "requirement": {"type": "clicks", "value": 1000},
        "reward": {"type": "multiplier", "value": 0.01}
    },
    {
        "id": "ach_bananas_3",
        "name": "Banana Hoarder",
        "description": "Collect 10,000 bananas",
        "requirement": {"type": "bananas", "value": 10000},
        "reward": {"type": "multiplier", "value": 0.01}
    },
    {
        "id": "ach_bananas_4",
        "name": "Banana Millionaire",
        "description": "Collect 1,000,000 bananas",
        "requirement": {"type": "bananas", "value": 1000000},
        "reward": {"type": "multiplier", "value": 0.01}
    },
    {
        "id": "ach_prestige_1",
        "name": "Ascended",
        "description": "Prestige once",
        "requirement": {"type": "prestige", "value": 1},
        "reward": {"type": "multiplier", "value": 0.05}
    },
    {
        "id": "ach_prestige_2",
        "name": "Ascend addict",
        "description": "Prestige 10 times",
        "requirement": {"type": "prestige", "value": 10},
        "reward": {"type": "multiplier", "value": 0.05}
    },
    {
        "id": "ach_prestige_2",
        "name": "GOD",
        "description": "Prestige 100 times",
        "requirement": {"type": "prestige", "value": 10},
        "reward": {"type": "multiplier", "value": 0.05}
    }
]

AVAILABLE_SKINS = {
    "default": {"name": "Classic Banana", "cost": 0, "emoji": "🍌"},
    "pixel": {"name": "Pixel Banana", "cost": 50000, "emoji": "🟨"},
    "shiny": {"name": "Shiny Banana", "cost": 5000000, "emoji": "✨"},
    "rolling": {"name": "Rolling Banana", "cost": 500000000, "emoji": "🛹"},
    "slippy": {"name": "Slippy Banana", "cost": 50000000000, "emoji": "🐍"},
    "cosmic": {"name": "Cosmic Banana", "cost": 5000000000000, "emoji": "🌌"},
    "golden": {"name": "Golden Banana", "cost": 500000000000000, "emoji": "⭐"}
}

SAVE_FILE = "/app/data/bananint_enhanced_data.json"

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
            "achievements_data": {
                sid: {aid: ach.dict() for aid, ach in achs.items()}
                for sid, achs in achievements_data.items()
            }
        }
        with open(SAVE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"❌ Error saving data: {e}")

def load_data():
    """Load game data from disk"""
    global game_sessions, upgrades_data, leaderboard_data, achievements_data
    
    if not os.path.exists(SAVE_FILE):
        return
    
    try:
        with open(SAVE_FILE, "r") as f:
            data = json.load(f)
        
        game_sessions.clear()
        upgrades_data.clear()
        leaderboard_data.clear()
        achievements_data.clear()
        
        for sid, gs in data.get("game_sessions", {}).items():
            game_sessions[sid] = GameState(**gs)
        for sid, ups in data.get("upgrades_data", {}).items():
            upgrades_data[sid] = {uid: UpgradeType(**up) for uid, up in ups.items()}
        for lb in data.get("leaderboard_data", []):
            leaderboard_data.append(LeaderboardEntry(**lb))
        for sid, achs in data.get("achievements_data", {}).items():
            achievements_data[sid] = {aid: Achievement(**ach) for aid, ach in achs.items()}
    except Exception as e:
        print(f"❌ Error loading data: {e}")

load_data()

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
        playerName="",
        bananaDNA=0,
        totalBananasEarned=0,
        prestigeCount=0,
        selectedSkin="default",
        ownedSkins=["default"],
        activeBoosts=[],
        lastEventCheck=time.time() * 1000
    )

def create_default_upgrades(session_id: str) -> Dict[str, UpgradeType]:
    upgrades = {}
    for upgrade_data in DEFAULT_UPGRADES:
        upgrade = UpgradeType(**upgrade_data)
        upgrades[upgrade.id] = upgrade
    return upgrades

def create_default_achievements(session_id: str) -> Dict[str, Achievement]:
    achievements = {}
    for ach_data in DEFAULT_ACHIEVEMENTS:
        achievement = Achievement(**ach_data)
        achievements[achievement.id] = achievement
    return achievements

def calculate_upgrade_cost(upgrade: UpgradeType, use_dna: bool = False) -> int:
    """Cost increases by 15% per owned upgrade, or flat DNA cost for prestige"""
    if upgrade.type == "prestige":
        return upgrade.baseCost  # Flat DNA cost
    return math.floor(upgrade.baseCost * math.pow(1.15, upgrade.owned))

def get_global_multiplier(game_state: GameState, upgrades: Dict[str, UpgradeType], achievements: Dict[str, Achievement]) -> float:
    """Calculate global multiplier from DNA, synergies, achievements"""
    multiplier = 1.0
    
    # DNA bonus: +1% per DNA
    multiplier += game_state.bananaDNA * 0.01
    
    # Prestige upgrades
    if "prestige_1" in upgrades and upgrades["prestige_1"].owned > 0:
        multiplier *= math.pow(upgrades["prestige_1"].multiplier, upgrades["prestige_1"].owned)
    
    # Achievement bonuses
    for ach in achievements.values():
        if ach.unlocked and ach.reward.get("type") == "multiplier":
            multiplier += ach.reward.get("value", 0)
    
    # Active boosts
    for boost in game_state.activeBoosts:
        if boost.get("active", False):
            multiplier *= boost.get("multiplier", 0)
    
    return multiplier

def calculate_bananas_per_second(upgrades: Dict[str, UpgradeType], game_state: GameState, achievements: Dict[str, Achievement]) -> float:
    """Calculate total bananas per second"""
    total = 0.0
    
    # Auto generators
    for upgrade in upgrades.values():
        if upgrade.type == "auto" and upgrade.owned > 0:
            total += upgrade.multiplier * upgrade.owned
    
    # Auto-clicker bots (synergy)
    if "synergy_1" in upgrades and upgrades["synergy_1"].owned > 0:
        bpc = calculate_bananas_per_click(upgrades, game_state, achievements)
        total += bpc * upgrades["synergy_1"].owned // 10
    
    # Prestige upgrade: Quantum Peel Generator
    if "prestige_2" in upgrades and upgrades["prestige_2"].owned > 0:
        total *= math.pow(upgrades["prestige_2"].multiplier, upgrades["prestige_2"].owned)
    
    # Apply global multiplier
    multiplier = get_global_multiplier(game_state, upgrades, achievements)
    return total * multiplier

def calculate_bananas_per_click(upgrades: Dict[str, UpgradeType], game_state: GameState, achievements: Dict[str, Achievement]) -> int:
    """Calculate total bananas per click"""
    total = 1
    
    # Click upgrades
    for upgrade in upgrades.values():
        if upgrade.type == "click" and upgrade.owned > 0:
            total += upgrade.multiplier * upgrade.owned
    
    # Photosynthetic Bananas synergy: auto upgrades boost clicks by 10%
    if "synergy_2" in upgrades and upgrades["synergy_2"].owned > 0:
        auto_count = sum(u.owned for u in upgrades.values() if u.type == "auto")
        total += int(auto_count * 0.1 * total)
    
    # Apply global multiplier
    multiplier = get_global_multiplier(game_state, upgrades, achievements)
    return int(total * multiplier)

def check_achievements(game_state: GameState, achievements: Dict[str, Achievement]) -> List[Achievement]:
    """Check and unlock achievements"""
    newly_unlocked = []
    
    for ach in achievements.values():
        if ach.unlocked:
            continue
        
        req_type = ach.requirement.get("type")
        req_value = ach.requirement.get("value")
        
        unlocked = False
        if req_type == "clicks":
            unlocked = game_state.totalClicks >= req_value
        elif req_type == "bananas":
            unlocked = game_state.totalBananasEarned >= req_value
        elif req_type == "prestige":
            unlocked = game_state.prestigeCount >= req_value
        
        if unlocked:
            ach.unlocked = True
            ach.unlockedAt = datetime.utcnow().isoformat()
            newly_unlocked.append(ach)
    
    return newly_unlocked

def spawn_random_event(session_id: str) -> Optional[ActiveEvent]:
    """Randomly spawn events"""
    # 5% chance per check
    if random.random() > 0.05:
        return None
    
    event_type = random.choice(["rain", "festival", "golden"])
    event_id = f"event-{session_id}-{int(time.time())}"
    
    if event_type == "rain":
        event = ActiveEvent(
            id=event_id,
            type="rain",
            startTime=time.time() * 1000,
            duration=60,
            multiplier=2.0
        )
    elif event_type == "festival":
        event = ActiveEvent(
            id=event_id,
            type="festival",
            startTime=time.time() * 1000,
            duration=120,
            multiplier=1.0
        )
    elif event_type == "golden":
        event = ActiveEvent(
            id=event_id,
            type="golden",
            startTime=time.time() * 1000,
            duration=10,
            multiplier=1.0
        )
    
    active_events[event_id] = event
    return event

def get_active_events(session_id: str) -> List[ActiveEvent]:
    """Get active events for a session"""
    current_time = time.time() * 1000
    active = []
    
    for event_id, event in list(active_events.items()):
        if event_id.startswith(f"event-{session_id}"):
            if current_time - event.startTime < event.duration * 1000:
                active.append(event)
            else:
                del active_events[event_id]
    
    return active

def sanitize_leaderboard(entries: List[LeaderboardEntry]) -> List[PublicLeaderboardEntry]:
    """Remove sessionId from leaderboard entries"""
    return [
        PublicLeaderboardEntry(
            name=entry.name,
            score=entry.score,
            date=entry.date,
            prestigeCount=entry.prestigeCount
        )
        for entry in entries
    ]

def update_leaderboard(session_id: str, player_name: str, score: int, prestige_count: int) -> List[PublicLeaderboardEntry]:
    """Update leaderboard"""
    load_data()
    
    existing_entry = next((e for e in leaderboard_data if e.sessionId == session_id), None)
    
    if existing_entry:
        if score > existing_entry.score:
            existing_entry.score = score
            existing_entry.name = player_name
            existing_entry.date = datetime.utcnow().isoformat()
            existing_entry.prestigeCount = prestige_count
    else:
        leaderboard_data.append(
            LeaderboardEntry(
                name=player_name[:20],
                score=score,
                date=datetime.utcnow().isoformat(),
                sessionId=session_id,
                prestigeCount=prestige_count
            )
        )
    
    leaderboard_data[:] = sorted(leaderboard_data, key=lambda x: x.score, reverse=True)[:10]
    save_data()
    
    return sanitize_leaderboard(leaderboard_data)

def get_leaderboard() -> List[PublicLeaderboardEntry]:
    """Get current leaderboard"""
    top_entries = sorted(leaderboard_data, key=lambda x: x.score, reverse=True)[:10]
    return sanitize_leaderboard(top_entries)

# API Endpoints
@router.post("/init", response_model=InitResponse)
async def init_game(request: InitRequest):
    """Initialize or restore game session"""
    session_id = request.sessionId
    
    if session_id and session_id in game_sessions:
        game_state = game_sessions[session_id]
        upgrades = upgrades_data[session_id]
        achievements = achievements_data.get(session_id, create_default_achievements(session_id))
    else:
        session_id = generate_session_id()
        game_state = create_initial_state(session_id)
        upgrades = create_default_upgrades(session_id)
        achievements = create_default_achievements(session_id)
        
        game_sessions[session_id] = game_state
        upgrades_data[session_id] = upgrades
        achievements_data[session_id] = achievements
    
    # Update stats
    game_state.bananasPerClick = calculate_bananas_per_click(upgrades, game_state, achievements)
    game_state.bananasPerSecond = calculate_bananas_per_second(upgrades, game_state, achievements)
    
    # Check for events
    events = get_active_events(session_id)
    
    return InitResponse(
        sessionId=session_id,
        gameState=game_state,
        upgrades=list(upgrades.values()),
        leaderboard=get_leaderboard(),
        playerName=game_state.playerName or "",
        achievements=list(achievements.values()),
        activeEvents=events
    )

@router.post("/sync", response_model=SyncResponse)
async def sync_game(request: SyncRequest):
    """Sync game state"""
    if request.sessionId not in game_sessions:
        return SyncResponse(
            success=False,
            gameState=create_initial_state(request.sessionId),
            leaderboard=get_leaderboard(),
            achievements=[],
            activeEvents=[],
            message="Invalid session"
        )
    
    game_state = game_sessions[request.sessionId]
    upgrades = upgrades_data[request.sessionId]
    achievements = achievements_data[request.sessionId]
    current_time = time.time() * 1000
    
    # Validate clicks
    time_since_last = (current_time - game_state.lastSyncTime) / 1000
    max_clicks = math.ceil(time_since_last * 20)
    actual_clicks = min(request.pendingClicks, max_clicks)
    
    # Calculate earnings
    click_earnings = actual_clicks * game_state.bananasPerClick
    
    # Time-based earnings with event multiplier
    time_earnings = game_state.bananasPerSecond * time_since_last
    
    # Apply event multipliers
    events = get_active_events(request.sessionId)
    for event in events:
        if event.type == "rain":
            time_earnings *= event.multiplier
    
    total_earned = time_earnings + click_earnings
    game_state.bananas += total_earned
    game_state.totalBananasEarned += total_earned
    game_state.totalClicks += actual_clicks
    game_state.lastSyncTime = current_time
    
    # Update stats
    game_state.bananasPerClick = calculate_bananas_per_click(upgrades, game_state, achievements)
    game_state.bananasPerSecond = calculate_bananas_per_second(upgrades, game_state, achievements)
    
    # Check achievements
    check_achievements(game_state, achievements)
    
    # Maybe spawn event
    if current_time - game_state.lastEventCheck > 60000:  # Check every minute
        new_event = spawn_random_event(request.sessionId)
        if new_event:
            events.append(new_event)
        game_state.lastEventCheck = current_time
    
    # Auto-update leaderboard
    updated_leaderboard = get_leaderboard()
    if game_state.playerName and game_state.playerName.strip():
        updated_leaderboard = update_leaderboard(
            request.sessionId,
            game_state.playerName,
            int(game_state.bananas),
            game_state.prestigeCount
        )
    
    save_data()
    
    return SyncResponse(
        success=True,
        gameState=game_state,
        leaderboard=updated_leaderboard,
        achievements=list(achievements.values()),
        activeEvents=events
    )

@router.post("/upgrade", response_model=UpgradeResponse)
async def buy_upgrade(request: UpgradeRequest):
    """Purchase upgrade"""
    if request.sessionId not in game_sessions:
        return UpgradeResponse(
            success=False,
            gameState=create_initial_state(request.sessionId),
            upgrades=[],
            leaderboard=get_leaderboard(),
            achievements=[],
            message="Invalid session"
        )
    
    game_state = game_sessions[request.sessionId]
    upgrades = upgrades_data[request.sessionId]
    achievements = achievements_data[request.sessionId]
    
    if request.upgradeId not in upgrades:
        return UpgradeResponse(
            success=False,
            gameState=game_state,
            upgrades=list(upgrades.values()),
            leaderboard=get_leaderboard(),
            achievements=list(achievements.values()),
            message="Invalid upgrade"
        )
    
    upgrade = upgrades[request.upgradeId]
    
    # Check unlock requirements
    if upgrade.unlockRequirement:
        if "prestigeCount" in upgrade.unlockRequirement:
            if game_state.prestigeCount < upgrade.unlockRequirement["prestigeCount"]:
                return UpgradeResponse(
                    success=False,
                    gameState=game_state,
                    upgrades=list(upgrades.values()),
                    leaderboard=get_leaderboard(),
                    achievements=list(achievements.values()),
                    message=f"Need {cost} bananas"
            )
        game_state.bananas -= cost
    

    # Calculate cost
    if upgrade.type == "prestige":
        cost = calculate_upgrade_cost(upgrade, use_dna=True)
        if game_state.bananaDNA < cost:
            return UpgradeResponse(
                success=False,
                gameState=game_state,
                upgrades=list(upgrades.values()),
                leaderboard=get_leaderboard(),
                achievements=list(achievements.values()),
                message=f"Need {cost} DNA"
            )
        game_state.bananaDNA -= cost
    else:
        cost = calculate_upgrade_cost(upgrade)
        if game_state.bananas < cost:
            return UpgradeResponse(
                success=False,
                gameState=game_state,
                upgrades=list(upgrades.values()),
                leaderboard=get_leaderboard(),
                achievements=list(achievements.values()),
                message=f"Requires {upgrade.unlockRequirement['prestigeCount']} prestige(s)"
            )

    upgrade.owned += 1
    
    # Recalculate stats
    game_state.bananasPerClick = calculate_bananas_per_click(upgrades, game_state, achievements)
    game_state.bananasPerSecond = calculate_bananas_per_second(upgrades, game_state, achievements)
    
    # Auto-update leaderboard
    updated_leaderboard = get_leaderboard()
    if game_state.playerName and game_state.playerName.strip():
        updated_leaderboard = update_leaderboard(
            request.sessionId,
            game_state.playerName,
            int(game_state.bananas),
            game_state.prestigeCount
        )
    
    save_data()
    
    return UpgradeResponse(
        success=True,
        gameState=game_state,
        upgrades=list(upgrades.values()),
        leaderboard=updated_leaderboard,
        achievements=list(achievements.values())
    )

@router.post("/prestige", response_model=PrestigeResponse)
async def prestige_game(request: PrestigeRequest):
    """Prestige (ascend) - reset progress for DNA"""
    if request.sessionId not in game_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    game_state = game_sessions[request.sessionId]
    
    # Requirement: 1 billion bananas minimum
    if game_state.totalBananasEarned < 1_000_000_000:
        return PrestigeResponse(
            success=False,
            gameState=game_state,
            upgrades=[],
            bananaDNAGained=0,
            message="Need 1 billion lifetime bananas to prestige"
        )
    
    # Calculate DNA gained (1 DNA per 100M lifetime bananas)
    dna_gained = int(game_state.totalBananasEarned / 100_000_000)
    
    # Keep: DNA, prestige count, player name, skins, achievements
    old_dna = game_state.bananaDNA
    old_name = game_state.playerName
    old_skins = game_state.ownedSkins.copy()
    old_selected_skin = game_state.selectedSkin
    old_prestige_count = game_state.prestigeCount
    
    # Get prestige upgrades
    old_upgrades = upgrades_data[request.sessionId]
    prestige_upgrades = {k: v for k, v in old_upgrades.items() if v.type == "prestige"}
    
    # Keep achievements
    old_achievements = achievements_data[request.sessionId]
    
    # Reset everything else
    game_state.bananas = 0
    game_state.bananasPerClick = 1
    game_state.bananasPerSecond = 0
    game_state.totalClicks = 0
    game_state.totalBananasEarned = 0
    game_state.bananaDNA = old_dna + dna_gained
    game_state.prestigeCount = old_prestige_count + 1
    game_state.playerName = old_name
    game_state.ownedSkins = old_skins
    game_state.selectedSkin = old_selected_skin
    game_state.activeBoosts = []
    game_state.lastSyncTime = time.time() * 1000
    
    # Reset upgrades but keep prestige ones
    new_upgrades = create_default_upgrades(request.sessionId)
    for upgrade_id, upgrade in prestige_upgrades.items():
        if upgrade_id in new_upgrades:
            new_upgrades[upgrade_id] = upgrade
    
    upgrades_data[request.sessionId] = new_upgrades
    
    # Keep achievements
    achievements_data[request.sessionId] = old_achievements
    
    # Check prestige achievement
    check_achievements(game_state, old_achievements)
    
    # Recalculate stats
    game_state.bananasPerClick = calculate_bananas_per_click(new_upgrades, game_state, old_achievements)
    game_state.bananasPerSecond = calculate_bananas_per_second(new_upgrades, game_state, old_achievements)
    
    save_data()
    
    return PrestigeResponse(
        success=True,
        gameState=game_state,
        upgrades=list(new_upgrades.values()),
        bananaDNAGained=dna_gained,
        message=f"Ascended! Gained {dna_gained} Banana DNA"
    )

@router.post("/buy-skin")
async def buy_skin(request: SkinRequest):
    """Buy a cosmetic skin"""
    if request.sessionId not in game_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    game_state = game_sessions[request.sessionId]
    
    if request.skinId not in AVAILABLE_SKINS:
        raise HTTPException(status_code=400, detail="Invalid skin")
    
    skin = AVAILABLE_SKINS[request.skinId]
    
    if request.skinId in game_state.ownedSkins:
        # Already owned, just equip
        game_state.selectedSkin = request.skinId
        save_data()
        return {"success": True, "message": f"Equipped {skin['name']}", "gameState": game_state}
    
    # Purchase
    if game_state.bananas < skin["cost"]:
        raise HTTPException(status_code=400, detail="Not enough bananas")
    
    game_state.bananas -= skin["cost"]
    game_state.ownedSkins.append(request.skinId)
    game_state.selectedSkin = request.skinId
    
    save_data()
    
    return {"success": True, "message": f"Purchased {skin['name']}!", "gameState": game_state}

@router.post("/click-event")
async def click_event(request: EventClickRequest):
    """Click on a special event (e.g., golden banana)"""
    if request.sessionId not in game_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if request.eventId not in active_events:
        raise HTTPException(status_code=400, detail="Event expired or invalid")
    
    event = active_events[request.eventId]
    game_state = game_sessions[request.sessionId]
    
    if event.type == "golden":
        # Golden banana: award 1% of total bananas
        reward = max(int(game_state.bananas * 0.01), 100)
        game_state.bananas += reward
        game_state.totalBananasEarned += reward
        
        # Remove event
        del active_events[request.eventId]
        
        save_data()
        return {"success": True, "reward": reward, "message": f"Golden banana! +{reward} bananas!"}
    
    raise HTTPException(status_code=400, detail="Event not clickable")

@router.post("/submit-score")
async def submit_score(request):
    """Submit score to leaderboard"""
    if request.sessionId not in game_sessions:
        return {"success": False, "message": "Invalid session"}
    
    game_state = game_sessions[request.sessionId]
    trimmed_name = request.name.strip()
    
    if not trimmed_name:
        return {"success": False, "message": "Name cannot be empty"}
    
    game_state.playerName = trimmed_name
    
    updated_leaderboard = update_leaderboard(
        request.sessionId,
        trimmed_name,
        int(game_state.bananas),
        game_state.prestigeCount
    )
    
    save_data()
    
    return {"success": True, "leaderboard": updated_leaderboard, "message": "Score submitted!"}

@router.post("/reset")
async def reset_game(request):
    """Reset game session"""
    if request.sessionId not in game_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    initial_state = create_initial_state(request.sessionId)
    initial_upgrades = create_default_upgrades(request.sessionId)
    initial_achievements = create_default_achievements(request.sessionId)
    
    game_sessions[request.sessionId] = initial_state
    upgrades_data[request.sessionId] = initial_upgrades
    achievements_data[request.sessionId] = initial_achievements
    
    save_data()
    return {
        "success": True,
        "gameState": initial_state,
        "upgrades": list(initial_upgrades.values())
    }

@router.get("/leaderboard")
async def get_leaderboard_endpoint():
    """Get leaderboard"""
    return get_leaderboard()

@router.get("/skins")
async def get_skins():
    """Get available skins"""
    return AVAILABLE_SKINS

@router.get("/")
async def root():
    return {"message": "Banana Clicker API - Enhanced Edition"}