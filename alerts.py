"""
Trade Alert System: Real-Time Portfolio Notifications

Sends alerts via:
- Console output (always)
- Slack webhook (if configured)
- Email digest (if configured)
- Dashboard history (tracked in memory)

Alert Types:
- POSITION_OPENED: New trade started
- PROFIT_TARGET_HIT: Position reached 50% of target (take partial profits)
- STOP_LOSS_IMMINENT: Stock within 2% of stop loss
- POSITION_CLOSED: Trade exited (stop, target, max hold)
- HOLD_WARNING: Position approaching 10-day auto-close
- NEW_SETUP: High-confidence trade opportunity (moat + recovery)
- REGIME_CHANGE: Market regime shifted
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import requests
from dotenv import load_dotenv

load_dotenv()


class AlertManager:
    """Manages portfolio alerts across multiple channels."""

    ALERT_TYPES = {
        "POSITION_OPENED": {"icon": "📈", "color": "green", "priority": "LOW"},
        "PROFIT_TARGET_HIT": {"icon": "🎯", "color": "blue", "priority": "HIGH"},
        "STOP_LOSS_IMMINENT": {"icon": "⚠️", "color": "yellow", "priority": "CRITICAL"},
        "POSITION_CLOSED": {"icon": "🏁", "color": "gray", "priority": "MEDIUM"},
        "HOLD_WARNING": {"icon": "⏰", "color": "orange", "priority": "MEDIUM"},
        "NEW_SETUP": {"icon": "🚀", "color": "green", "priority": "HIGH"},
        "REGIME_CHANGE": {"icon": "🔄", "color": "purple", "priority": "HIGH"},
        "LOSS_LIMIT_HIT": {"icon": "🔴", "color": "red", "priority": "CRITICAL"}
    }

    def __init__(self):
        self.slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        self.email_enabled = os.getenv("EMAIL_SERVICE", "").lower() == "sendgrid"
        self.sendgrid_api_key = os.getenv("SENDGRID_API_KEY")
        self.alert_email = os.getenv("ALERT_EMAIL", "user@example.com")

        # In-memory alert history (for dashboard)
        self.alert_history = []
        self.daily_digest = []

    def send_alert(
        self,
        alert_type: str,
        ticker: str,
        trigger: str,
        data: Dict = None,
        immediate: bool = True
    ) -> bool:
        """
        Send alert across all configured channels.

        Args:
            alert_type: Type of alert (from ALERT_TYPES)
            ticker: Stock ticker
            trigger: What triggered the alert (e.g., "Stop loss hit at $50.00")
            data: Additional context (price, target, position size, etc.)
            immediate: If False, queue for daily digest instead

        Returns:
            bool: True if sent successfully
        """
        if data is None:
            data = {}

        alert_info = self.ALERT_TYPES.get(alert_type, {})
        icon = alert_info.get("icon", "📌")
        priority = alert_info.get("priority", "MEDIUM")

        # Create alert message
        alert_message = self._format_alert_message(
            alert_type, icon, ticker, trigger, data
        )

        # Store in history
        alert_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": alert_type,
            "ticker": ticker,
            "priority": priority,
            "trigger": trigger,
            "message": alert_message,
            "data": data,
            "acknowledged": False
        }

        self.alert_history.append(alert_entry)

        # Queue for daily digest OR send immediately
        if not immediate:
            self.daily_digest.append(alert_entry)
            return True

        # Console output (always)
        print(f"\n{icon} ALERT [{priority}] {ticker}: {trigger}")

        # Slack (if configured)
        if self.slack_webhook_url:
            self._send_slack(alert_type, icon, ticker, trigger, data, priority)

        # Email (if critical)
        if self.email_enabled and priority == "CRITICAL":
            self._send_email(alert_type, ticker, trigger, data)

        return True

    def _format_alert_message(
        self, alert_type: str, icon: str, ticker: str, trigger: str, data: Dict
    ) -> str:
        """Format alert message for display."""
        message = f"{icon} **{alert_type.replace('_', ' ')}**\n"
        message += f"Ticker: {ticker}\n"
        message += f"Trigger: {trigger}\n"

        if data:
            message += "\nDetails:\n"
            for key, value in data.items():
                message += f"  • {key}: {value}\n"

        return message

    def _send_slack(
        self, alert_type: str, icon: str, ticker: str, trigger: str, data: Dict, priority: str
    ):
        """Send alert to Slack webhook."""
        try:
            # Color based on priority
            color_map = {
                "CRITICAL": "#FF0000",  # Red
                "HIGH": "#FF9900",  # Orange
                "MEDIUM": "#0099CC",  # Blue
                "LOW": "#00CC00"  # Green
            }

            color = color_map.get(priority, "#0099CC")

            # Build Slack message
            slack_message = {
                "attachments": [
                    {
                        "color": color,
                        "title": f"{icon} {alert_type.replace('_', ' ')} — {ticker}",
                        "text": trigger,
                        "fields": [
                            {
                                "title": "Priority",
                                "value": priority,
                                "short": True
                            },
                            {
                                "title": "Time",
                                "value": datetime.now().strftime("%H:%M:%S"),
                                "short": True
                            }
                        ] + [
                            {
                                "title": key.replace("_", " ").title(),
                                "value": str(value),
                                "short": True
                            }
                            for key, value in list(data.items())[:4]  # Max 4 fields
                        ],
                        "footer": "Stock Agent Alert System",
                        "ts": int(datetime.now().timestamp())
                    }
                ]
            }

            response = requests.post(
                self.slack_webhook_url,
                json=slack_message,
                timeout=5
            )

            return response.status_code == 200

        except Exception as e:
            print(f"❌ Slack alert error: {str(e)[:50]}")
            return False

    def _send_email(self, alert_type: str, ticker: str, trigger: str, data: Dict):
        """Send email alert (stub - requires SendGrid setup)."""
        try:
            # This is a stub - full implementation requires SendGrid API
            # For now, just log to console
            print(f"📧 Email alert queued for {self.alert_email}")
            return True
        except Exception as e:
            print(f"❌ Email alert error: {str(e)[:50]}")
            return False

    def send_daily_digest(self) -> str:
        """
        Generate and send daily alert summary.

        Returns:
            str: Formatted digest message
        """
        if not self.daily_digest:
            return "No alerts today."

        digest = f"\n📋 DAILY ALERT DIGEST — {datetime.now().strftime('%Y-%m-%d')}\n"
        digest += "=" * 60 + "\n\n"

        # Group by alert type
        by_type = {}
        for alert in self.daily_digest:
            alert_type = alert["type"]
            if alert_type not in by_type:
                by_type[alert_type] = []
            by_type[alert_type].append(alert)

        # Format by type
        for alert_type, alerts in by_type.items():
            icon = self.ALERT_TYPES.get(alert_type, {}).get("icon", "📌")
            digest += f"{icon} {alert_type.replace('_', ' ')} ({len(alerts)})\n"

            for alert in alerts:
                digest += f"  • {alert['ticker']}: {alert['trigger']}\n"

            digest += "\n"

        digest += "=" * 60 + "\n"
        digest += "Check dashboard for full details.\n"

        # Clear digest
        self.daily_digest = []

        return digest

    def get_alert_history(self, hours: int = 24, limit: int = 50) -> List[Dict]:
        """
        Get recent alerts for dashboard display.

        Args:
            hours: Show alerts from last N hours
            limit: Maximum number to return

        Returns:
            List of alert entries
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)

        recent_alerts = [
            alert for alert in self.alert_history
            if datetime.fromisoformat(alert["timestamp"]) > cutoff_time
        ]

        return recent_alerts[-limit:]  # Most recent first

    def acknowledge_alert(self, alert_index: int) -> bool:
        """Mark an alert as acknowledged."""
        try:
            self.alert_history[alert_index]["acknowledged"] = True
            self.alert_history[alert_index]["acknowledged_at"] = datetime.now().isoformat()
            return True
        except IndexError:
            return False


# Global alert manager instance
alert_manager = AlertManager()


# Convenience functions
def send_position_opened_alert(ticker: str, entry_price: float, target: float, stop: float, size: float):
    """Alert when new position is opened."""
    alert_manager.send_alert(
        "POSITION_OPENED",
        ticker,
        f"Opened at £{entry_price:.2f}",
        {
            "Entry Price": f"£{entry_price:.2f}",
            "Target": f"£{target:.2f}",
            "Stop Loss": f"£{stop:.2f}",
            "Position Size": f"£{size:.2f}",
            "Risk": f"£{abs(entry_price - stop):.2f}"
        }
    )


def send_profit_target_alert(ticker: str, current_price: float, pnl: float, pnl_pct: float):
    """Alert when position hits 50% of profit target."""
    alert_manager.send_alert(
        "PROFIT_TARGET_HIT",
        ticker,
        f"Position at +{pnl_pct:.1f}% ({'+' if pnl > 0 else ''}£{pnl:.2f})",
        {
            "Current Price": f"£{current_price:.2f}",
            "P&L": f"£{pnl:.2f}",
            "P&L %": f"{pnl_pct:+.1f}%",
            "Action": "Consider taking partial profits"
        },
        immediate=True
    )


def send_stop_loss_alert(ticker: str, current_price: float, stop_price: float):
    """Alert when stock approaches stop loss."""
    distance = abs(current_price - stop_price)
    distance_pct = (distance / stop_price) * 100

    alert_manager.send_alert(
        "STOP_LOSS_IMMINENT",
        ticker,
        f"Within {distance_pct:.1f}% of stop loss",
        {
            "Current Price": f"£{current_price:.2f}",
            "Stop Loss": f"£{stop_price:.2f}",
            "Distance": f"£{distance:.2f} ({distance_pct:.1f}%)"
        },
        immediate=True
    )


def send_position_closed_alert(ticker: str, exit_reason: str, exit_price: float, pnl: float, pnl_pct: float):
    """Alert when position is closed."""
    alert_manager.send_alert(
        "POSITION_CLOSED",
        ticker,
        f"Closed ({exit_reason}) at £{exit_price:.2f}",
        {
            "Exit Reason": exit_reason,
            "Exit Price": f"£{exit_price:.2f}",
            "P&L": f"£{pnl:.2f}",
            "P&L %": f"{pnl_pct:+.1f}%"
        },
        immediate=True
    )


def send_new_setup_alert(ticker: str, moat_score: float, recovery_prob: float, score: int):
    """Alert on new high-conviction setup."""
    alert_manager.send_alert(
        "NEW_SETUP",
        ticker,
        f"High-conviction setup detected",
        {
            "Moat Score": f"{moat_score:.1f}/5.0",
            "Recovery Prob": f"{recovery_prob*100:.0f}%",
            "Technical Score": score,
            "Action": "Review for entry"
        },
        immediate=False  # Queue for daily digest
    )


def send_regime_change_alert(old_regime: str, new_regime: str):
    """Alert on market regime change."""
    alert_manager.send_alert(
        "REGIME_CHANGE",
        "SPY",
        f"Market regime shifted {old_regime} → {new_regime}",
        {
            "Old Regime": old_regime,
            "New Regime": new_regime,
            "Action": "Review position sizing and strategy"
        },
        immediate=True
    )
