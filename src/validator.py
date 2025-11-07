"""
Banana Clicker - Game State Validation Debugger

This module helps diagnose validation failures and identify issues
with the anti-cheat system.
"""

import json
import math
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ValidationReport:
    """Detailed validation report for a game session"""
    session_id: str
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    
    # Calculated values
    max_from_clicks: float
    max_from_time: float
    total_spent: float
    max_possible: float
    current_with_spending: float
    tolerance: float
    
    # State info
    current_bananas: float
    total_clicks: int
    bananas_per_click: int
    bananas_per_second: float
    time_played_seconds: float
    
    # Upgrade info
    click_upgrades: List[Dict]
    auto_upgrades: List[Dict]
    
    def __str__(self):
        report = [
            f"\n{'='*70}",
            f"VALIDATION REPORT - {self.session_id}",
            f"{'='*70}",
            f"Status: {'✅ VALID' if self.is_valid else '❌ INVALID'}",
            f"",
            f"CURRENT STATE:",
            f"  Bananas: {self.current_bananas:,.2f}",
            f"  Total Clicks: {self.total_clicks:,}",
            f"  Bananas/Click: {self.bananas_per_click}",
            f"  Bananas/Second: {self.bananas_per_second:.2f}",
            f"  Time Played: {self.time_played_seconds/3600:.2f} hours",
            f"",
            f"EARNINGS BREAKDOWN:",
            f"  Max from Clicks: {self.max_from_clicks:,.2f}",
            f"  Max from Time: {self.max_from_time:,.2f}",
            f"  Total Spent on Upgrades: {self.total_spent:,.2f}",
            f"  ─────────────────────────",
            f"  Max Possible Total: {self.max_possible:,.2f}",
            f"  Current + Spending: {self.current_with_spending:,.2f}",
            f"  Tolerance (10%): {self.tolerance:,.2f}",
            f"  Difference: {self.current_with_spending - self.max_possible:,.2f}",
            f"",
        ]
        
        if self.click_upgrades:
            report.append("CLICK UPGRADES:")
            for u in self.click_upgrades:
                cost_spent = sum(
                    math.floor(u['baseCost'] * math.pow(1.15, n))
                    for n in range(u['owned'])
                )
                report.append(f"  {u['name']}: {u['owned']}x (spent: {cost_spent:,})")
            report.append("")
        
        if self.auto_upgrades:
            report.append("AUTO UPGRADES:")
            for u in self.auto_upgrades:
                cost_spent = sum(
                    math.floor(u['baseCost'] * math.pow(1.15, n))
                    for n in range(u['owned'])
                )
                report.append(f"  {u['name']}: {u['owned']}x (spent: {cost_spent:,}, generates: {u['multiplier']*u['owned']}/s)")
            report.append("")
        
        if self.errors:
            report.append("ERRORS:")
            for error in self.errors:
                report.append(f"  ❌ {error}")
            report.append("")
        
        if self.warnings:
            report.append("WARNINGS:")
            for warning in self.warnings:
                report.append(f"  ⚠️  {warning}")
            report.append("")
        
        report.append(f"{'='*70}\n")
        return "\n".join(report)


class GameStateValidator:
    """Validates game states and provides detailed debugging information"""
    
    def __init__(self, save_file: str = "/app/data/bananint_data.json"):
        self.save_file = save_file
        self.data = None
        self.load_data()
    
    def load_data(self):
        """Load game data from file"""
        try:
            with open(self.save_file, 'r') as f:
                self.data = json.load(f)
            print(f"✅ Loaded data from {self.save_file}")
            print(f"   Sessions: {len(self.data.get('game_sessions', {}))}")
            print(f"   Leaderboard: {len(self.data.get('leaderboard_data', []))}")
        except FileNotFoundError:
            print(f"❌ File not found: {self.save_file}")
            self.data = {"game_sessions": {}, "upgrades_data": {}, "leaderboard_data": []}
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON: {e}")
            self.data = {"game_sessions": {}, "upgrades_data": {}, "leaderboard_data": []}
    
    @staticmethod
    def calculate_total_spent(upgrades: List[Dict]) -> float:
        """Calculate total bananas spent on upgrades"""
        total = 0
        for upgrade in upgrades:
            if upgrade['owned'] > 0:
                for n in range(upgrade['owned']):
                    cost = math.floor(upgrade['baseCost'] * math.pow(1.15, n))
                    total += cost
        return float(total)
    
    @staticmethod
    def calculate_bananas_per_click(upgrades: List[Dict]) -> int:
        """Calculate total bananas per click"""
        total = 1
        for upgrade in upgrades:
            if upgrade['type'] == 'click' and upgrade['owned'] > 0:
                total += upgrade['multiplier'] * upgrade['owned']
        return total
    
    @staticmethod
    def calculate_bananas_per_second(upgrades: List[Dict]) -> float:
        """Calculate total bananas per second"""
        total = 0.0
        for upgrade in upgrades:
            if upgrade['type'] == 'auto' and upgrade['owned'] > 0:
                total += upgrade['multiplier'] * upgrade['owned']
        return total
    
    def validate_session(self, session_id: str, verbose: bool = True) -> ValidationReport:
        """
        Validate a specific session and return detailed report
        
        THE BUG: The original validation doesn't account for the FULL SESSION LIFETIME.
        It only checks time since lastSyncTime, but players accumulate bananas over
        their entire play session through multiple syncs!
        """
        if not self.data or session_id not in self.data['game_sessions']:
            raise ValueError(f"Session {session_id} not found")
        
        game_state = self.data['game_sessions'][session_id]
        upgrades = list(self.data['upgrades_data'][session_id].values())
        
        errors = []
        warnings = []
        
        # Extract state
        current_bananas = game_state['bananas']
        total_clicks = game_state['totalClicks']
        bananas_per_click = game_state['bananasPerClick']
        bananas_per_second = game_state['bananasPerSecond']
        last_sync_time = game_state['lastSyncTime']
        
        # Calculate spending
        total_spent = self.calculate_total_spent(upgrades)
        
        # Calculate expected per-click and per-second
        expected_per_click = self.calculate_bananas_per_click(upgrades)
        expected_per_second = self.calculate_bananas_per_second(upgrades)
        
        # Validate per-click matches
        if bananas_per_click != expected_per_click:
            errors.append(f"bananasPerClick mismatch: expected {expected_per_click}, got {bananas_per_click}")
        
        # Validate per-second matches
        if abs(bananas_per_second - expected_per_second) > 0.1:
            errors.append(f"bananasPerSecond mismatch: expected {expected_per_second}, got {bananas_per_second}")
        
        # Calculate max possible earnings
        max_from_clicks = total_clicks * bananas_per_click
        
        # BUG FIX: Instead of using time since last sync, we need to calculate
        # the TOTAL time the session could have been active
        # The original code only checks time since lastSyncTime, which resets on each sync!
        
        # Extract session creation time from session_id
        session_creation_time = float(session_id.split('-')[1]) * 1000  # Convert to ms
        current_time = datetime.now().timestamp() * 1000
        total_session_time_seconds = (current_time - session_creation_time) / 1000
        
        # Apply 8-hour offline cap
        max_offline_seconds = 8 * 60 * 60
        capped_time = min(total_session_time_seconds, max_offline_seconds)
        
        # CRITICAL: We need to calculate max earnings considering AVERAGE bps over time
        # Players buy upgrades gradually, so their bps increases over time
        # Using current bps for the entire session is the bug!
        
        # However, we can still calculate a maximum bound:
        # Max time-based earnings = current_bps * capped_time
        # This assumes they had max bps the entire time (upper bound)
        max_from_time = bananas_per_second * capped_time
        
        max_possible = max_from_clicks + max_from_time
        current_with_spending = current_bananas + total_spent
        tolerance = max_possible * 0.1
        
        # Check if exceeds maximum
        if current_with_spending > max_possible + tolerance:
            errors.append(
                f"Impossible banana count: "
                f"max_possible={max_possible:.2f}, "
                f"current_with_spending={current_with_spending:.2f}"
            )
        
        # Warnings for edge cases
        if total_session_time_seconds > max_offline_seconds:
            warnings.append(f"Session longer than 8h offline cap ({total_session_time_seconds/3600:.1f}h)")
        
        if current_with_spending > max_possible * 0.5 and current_with_spending <= max_possible + tolerance:
            warnings.append("Close to maximum possible (might be legitimate, but verify)")
        
        # Separate upgrades by type
        click_upgrades = [u for u in upgrades if u['type'] == 'click' and u['owned'] > 0]
        auto_upgrades = [u for u in upgrades if u['type'] == 'auto' and u['owned'] > 0]
        
        report = ValidationReport(
            session_id=session_id,
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            max_from_clicks=max_from_clicks,
            max_from_time=max_from_time,
            total_spent=total_spent,
            max_possible=max_possible,
            current_with_spending=current_with_spending,
            tolerance=tolerance,
            current_bananas=current_bananas,
            total_clicks=total_clicks,
            bananas_per_click=bananas_per_click,
            bananas_per_second=bananas_per_second,
            time_played_seconds=total_session_time_seconds,
            click_upgrades=click_upgrades,
            auto_upgrades=auto_upgrades
        )
        
        if verbose:
            print(report)
        
        return report
    
    def validate_all_sessions(self, show_valid: bool = False) -> Dict[str, ValidationReport]:
        """Validate all sessions and return reports"""
        if not self.data:
            print("❌ No data loaded")
            return {}
        
        reports = {}
        sessions = self.data.get('game_sessions', {})
        
        print(f"\n🔍 Validating {len(sessions)} sessions...\n")
        
        invalid_count = 0
        for session_id in sessions:
            report = self.validate_session(session_id, verbose=False)
            reports[session_id] = report
            
            if not report.is_valid:
                invalid_count += 1
                print(report)
            elif show_valid:
                print(report)
        
        print(f"\n📊 SUMMARY:")
        print(f"   Total Sessions: {len(sessions)}")
        print(f"   Valid: {len(sessions) - invalid_count}")
        print(f"   Invalid: {invalid_count}")
        
        return reports
    
    def check_leaderboard_integrity(self):
        """Check if leaderboard entries match valid game states"""
        if not self.data:
            print("❌ No data loaded")
            return
        
        leaderboard = self.data.get('leaderboard_data', [])
        print(f"\n🏆 Checking {len(leaderboard)} leaderboard entries...\n")
        
        for entry in sorted(leaderboard, key=lambda x: x['score'], reverse=True):
            print(f"  {entry['name']}: {entry['score']:,} bananas ({entry['date']})")


# Example usage
if __name__ == "__main__":
    validator = GameStateValidator()
    
    # Check specific session
    session_id = "session-1762424258-64d1d09aba960c84"
    try:
        print(f"\n🔍 Validating specific session: {session_id}")
        report = validator.validate_session(session_id)
    except ValueError as e:
        print(f"❌ {e}")
    
    # Validate all sessions
    print("\n" + "="*70)
    validator.validate_all_sessions(show_valid=False)
    
    # Check leaderboard
    validator.check_leaderboard_integrity()