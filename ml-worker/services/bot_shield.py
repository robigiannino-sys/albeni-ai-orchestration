"""
Bot Shield — Anti-Competitor Click Fraud Detection
Albeni 1905 — Invisible Luxury Ecosystem

Rileva e blocca traffico fraudolento/bot dai competitor:
1. Behavioral Analysis: dwell time, mouse events, scroll depth
2. Pattern Detection: click velocity, IP clustering, user-agent anomalies
3. Budget Protection: stima €€ salvati escludendo click fraudolenti
4. Exclusion List: genera liste di IP/profili da escludere sulle piattaforme ADV
"""

import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ================================================================
# THREAT SIGNALS — Indicatori di Click Fraud
# ================================================================

class ThreatSignal:
    """Represents a suspicious behavior signal."""

    def __init__(self, signal_type: str, severity: float, details: Dict):
        self.signal_type = signal_type
        self.severity = severity  # 0.0 - 1.0
        self.details = details
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict:
        return {
            "type": self.signal_type,
            "severity": self.severity,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


# ================================================================
# BOT SHIELD SERVICE
# ================================================================

class BotShield:
    """
    Click fraud detection and budget protection.

    Analyzes behavioral signals to detect:
    - Competitor click attacks (very short dwell, no interaction)
    - Bot traffic (inhuman speed, no mouse/scroll)
    - Click farms (many clicks from same IP range)
    """

    # Threat score thresholds
    THREAT_LOW = 0.3
    THREAT_MEDIUM = 0.6
    THREAT_HIGH = 0.85

    def __init__(self):
        # In-memory storage (in production: Redis/DB)
        self._visitor_signals: Dict[str, List[ThreatSignal]] = defaultdict(list)
        self._ip_click_counts: Dict[str, List[float]] = defaultdict(list)  # IP → timestamps
        self._exclusion_list: Dict[str, Dict] = {}  # IP/fingerprint → exclusion details
        self._blocked_count: int = 0
        self._estimated_savings_eur: float = 0.0
        self._avg_cpc_eur: float = 1.20  # Average CPC estimate for Albeni's niche

    def analyze_visitor(
        self,
        visitor_id: str,
        ip_address: str,
        user_agent: str,
        dwell_time_ms: int,
        mouse_events: int,
        scroll_depth_pct: float,
        pages_viewed: int,
        session_duration_ms: int,
        is_paid: bool = False,
        referrer: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyze a visitor's behavior for fraud signals.

        Returns:
            {
                threat_score: 0.0-1.0,
                threat_level: "clean|low|medium|high|blocked",
                signals: [...],
                action: "allow|monitor|flag|block",
                should_exclude: bool,
            }
        """
        signals: List[ThreatSignal] = []

        # 1. DWELL TIME CHECK
        if dwell_time_ms < settings.ADV_BOT_DWELL_TIME_MIN_MS:
            severity = 1.0 if dwell_time_ms < 500 else 0.7
            signals.append(ThreatSignal(
                "ultra_short_dwell",
                severity,
                {"dwell_time_ms": dwell_time_ms, "threshold_ms": settings.ADV_BOT_DWELL_TIME_MIN_MS},
            ))

        # 2. MOUSE EVENTS CHECK (no interaction = likely bot)
        if mouse_events < settings.ADV_BOT_MIN_MOUSE_EVENTS:
            severity = 0.9 if mouse_events == 0 else 0.5
            signals.append(ThreatSignal(
                "no_mouse_interaction",
                severity,
                {"mouse_events": mouse_events, "threshold": settings.ADV_BOT_MIN_MOUSE_EVENTS},
            ))

        # 3. SCROLL DEPTH CHECK (0% scroll on content page = suspicious)
        if scroll_depth_pct < 5.0 and dwell_time_ms > 1000:
            signals.append(ThreatSignal(
                "zero_scroll",
                0.6,
                {"scroll_depth_pct": scroll_depth_pct},
            ))

        # 4. CLICK VELOCITY CHECK (too many pages too fast)
        if session_duration_ms > 0:
            pages_per_minute = (pages_viewed / (session_duration_ms / 60000.0))
            if pages_per_minute > settings.ADV_BOT_MAX_PAGES_PER_MIN:
                signals.append(ThreatSignal(
                    "inhuman_speed",
                    0.95,
                    {"pages_per_minute": round(pages_per_minute, 1), "threshold": settings.ADV_BOT_MAX_PAGES_PER_MIN},
                ))

        # 5. IP CLUSTERING CHECK (many clicks from same IP)
        now = time.time()
        self._ip_click_counts[ip_address].append(now)
        # Clean old entries (last 10 minutes)
        self._ip_click_counts[ip_address] = [
            t for t in self._ip_click_counts[ip_address] if now - t < 600
        ]
        ip_clicks_10min = len(self._ip_click_counts[ip_address])
        if ip_clicks_10min > 5:
            signals.append(ThreatSignal(
                "ip_cluster_attack",
                min(0.3 + (ip_clicks_10min - 5) * 0.15, 1.0),
                {"clicks_in_10min": ip_clicks_10min, "ip": ip_address},
            ))

        # 6. USER-AGENT ANOMALIES
        ua_lower = user_agent.lower()
        bot_indicators = ["bot", "spider", "crawler", "scraper", "headless", "phantom", "selenium", "puppeteer"]
        if any(b in ua_lower for b in bot_indicators):
            signals.append(ThreatSignal(
                "bot_user_agent",
                1.0,
                {"user_agent": user_agent[:100]},
            ))

        # 7. COMPETITOR REFERRER CHECK
        competitor_domains = ["smartwool.com", "icebreaker.com", "allbirds.com", "asket.com", "unboundmerino.com"]
        if referrer:
            ref_lower = referrer.lower()
            if any(c in ref_lower for c in competitor_domains):
                signals.append(ThreatSignal(
                    "competitor_referrer",
                    0.8,
                    {"referrer": referrer[:100]},
                ))

        # ---- CALCULATE THREAT SCORE ----
        if not signals:
            threat_score = 0.0
        else:
            # Weighted average, max capped at 1.0
            threat_score = min(
                sum(s.severity for s in signals) / max(len(signals), 1) * min(len(signals) * 0.4, 1.5),
                1.0
            )

        # Determine threat level and action
        if threat_score >= self.THREAT_HIGH:
            threat_level = "high"
            action = "block"
        elif threat_score >= self.THREAT_MEDIUM:
            threat_level = "medium"
            action = "flag"
        elif threat_score >= self.THREAT_LOW:
            threat_level = "low"
            action = "monitor"
        else:
            threat_level = "clean"
            action = "allow"

        should_exclude = threat_score >= self.THREAT_HIGH

        # Store signals for the visitor
        self._visitor_signals[visitor_id].extend(signals)

        # If blocking, add to exclusion list and count savings
        if should_exclude and is_paid:
            self._exclusion_list[ip_address] = {
                "visitor_id": visitor_id,
                "threat_score": threat_score,
                "signals": [s.to_dict() for s in signals],
                "excluded_at": datetime.utcnow().isoformat(),
                "ip": ip_address,
            }
            self._blocked_count += 1
            self._estimated_savings_eur += self._avg_cpc_eur

        result = {
            "visitor_id": visitor_id,
            "ip_address": ip_address,
            "threat_score": round(threat_score, 3),
            "threat_level": threat_level,
            "action": action,
            "should_exclude": should_exclude,
            "signals": [s.to_dict() for s in signals],
            "signal_count": len(signals),
            "is_paid_click": is_paid,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if should_exclude:
            logger.warning(
                f"BOT SHIELD: Blocking {ip_address} (score={threat_score:.2f}, "
                f"signals={len(signals)}, paid={is_paid})"
            )

        return result

    def get_exclusion_list(self) -> List[Dict]:
        """Get the current IP/fingerprint exclusion list for ad platform sync."""
        return [
            {
                "ip": ip,
                "threat_score": data["threat_score"],
                "excluded_at": data["excluded_at"],
                "signal_types": [s["type"] for s in data["signals"]],
            }
            for ip, data in self._exclusion_list.items()
        ]

    def get_stats(self) -> Dict:
        """Bot Shield statistics."""
        total_analyzed = sum(len(sigs) > 0 for sigs in self._visitor_signals.values())
        total_visitors = len(self._visitor_signals)

        # Signal type distribution
        signal_types: Dict[str, int] = defaultdict(int)
        for sigs in self._visitor_signals.values():
            for s in sigs:
                signal_types[s.signal_type] += 1

        return {
            "total_visitors_analyzed": total_visitors,
            "total_signals_detected": total_analyzed,
            "blocked_visitors": self._blocked_count,
            "exclusion_list_size": len(self._exclusion_list),
            "estimated_savings_eur": round(self._estimated_savings_eur, 2),
            "avg_cpc_eur": self._avg_cpc_eur,
            "signal_distribution": dict(signal_types),
            "block_rate": round(self._blocked_count / max(total_visitors, 1) * 100, 1),
        }

    def is_blocked(self, ip_address: str) -> bool:
        """Check if an IP is in the exclusion list."""
        return ip_address in self._exclusion_list
