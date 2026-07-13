"""
Notify tool — alert humans when agents need attention or finish work.

This closes the loop: agents run autonomously, notify you
when something matters. No polling. No babysitting.

Supports:
  - Slack (incoming webhook)
  - Email (SMTP — works with Gmail, Sendgrid, Mailgun, Postfix)
  - Generic webhook (POST JSON to any URL)
"""

import json
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any, Dict, List, Optional

import requests

from runtime.tools.base_tool import BaseTool, ToolResult
from runtime.llm.base import ToolDefinition


class NotifyTool(BaseTool):
    def __init__(
        self,
        slack_webhook_url: Optional[str] = None,
        smtp_host: Optional[str] = None,
        smtp_port: int = 587,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        smtp_from: Optional[str] = None,
        default_email_to: Optional[str] = None,
        default_webhook_url: Optional[str] = None,
    ):
        super().__init__(
            name="notify",
            description=(
                "Send a notification via Slack, email, or webhook. "
                "Use when a task completes, an error occurs, or human attention is needed."
            )
        )
        self.slack_webhook_url = slack_webhook_url
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.smtp_from = smtp_from
        self.default_email_to = default_email_to
        self.default_webhook_url = default_webhook_url

    def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        channel = input_data.get("channel", "slack")
        message = input_data.get("message", "").strip()
        subject = input_data.get("subject", "Agent notification")

        if not message:
            return ToolResult(success=False, output=None, error="No message provided")

        if channel == "slack":
            return self._send_slack(message)
        elif channel == "email":
            to = input_data.get("to") or self.default_email_to
            return self._send_email(to, subject, message)
        elif channel == "webhook":
            url = input_data.get("url") or self.default_webhook_url
            payload = input_data.get("payload") or {"message": message}
            return self._send_webhook(url, payload)
        else:
            return ToolResult(success=False, output=None, error=f"Unknown channel '{channel}'. Use: slack, email, webhook")

    def _send_slack(self, message: str) -> ToolResult:
        if not self.slack_webhook_url:
            return ToolResult(success=False, output=None, error="No Slack webhook URL configured (set slack_webhook_url)")

        try:
            resp = requests.post(
                self.slack_webhook_url,
                json={"text": message},
                timeout=10,
            )
            if resp.status_code == 200:
                return ToolResult(success=True, output={"channel": "slack", "status": "sent"})
            return ToolResult(success=False, output=None, error=f"Slack API error: {resp.status_code} {resp.text}")
        except Exception as e:
            return ToolResult(success=False, output=None, error=f"Slack send failed: {e}")

    def _send_email(self, to: Optional[str], subject: str, body: str) -> ToolResult:
        if not self.smtp_host:
            return ToolResult(success=False, output=None, error="No SMTP host configured")
        if not to:
            return ToolResult(success=False, output=None, error="No recipient (to) provided and no default_email_to set")
        if not self.smtp_user or not self.smtp_password:
            return ToolResult(success=False, output=None, error="SMTP credentials not configured (smtp_user, smtp_password)")

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.smtp_from or self.smtp_user
            msg["To"] = to
            msg.attach(MIMEText(body, "plain"))

            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.ehlo()
                server.starttls(context=context)
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(msg["From"], to, msg.as_string())

            return ToolResult(success=True, output={"channel": "email", "to": to, "subject": subject, "status": "sent"})
        except smtplib.SMTPAuthenticationError:
            return ToolResult(success=False, output=None, error="SMTP authentication failed — check smtp_user and smtp_password")
        except Exception as e:
            return ToolResult(success=False, output=None, error=f"Email send failed: {e}")

    def _send_webhook(self, url: Optional[str], payload: Any) -> ToolResult:
        if not url:
            return ToolResult(success=False, output=None, error="No webhook URL provided and no default_webhook_url set")

        try:
            resp = requests.post(url, json=payload, timeout=10)
            return ToolResult(
                success=resp.ok,
                output={"channel": "webhook", "url": url, "status_code": resp.status_code},
                error=None if resp.ok else f"Webhook returned {resp.status_code}"
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=f"Webhook send failed: {e}")

    def get_definition(self) -> ToolDefinition:
        channels = []
        if self.slack_webhook_url:
            channels.append("slack")
        if self.smtp_host:
            channels.append("email")
        channels.append("webhook")

        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema={
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                        "enum": ["slack", "email", "webhook"],
                        "description": f"Notification channel. Available: {', '.join(channels)}"
                    },
                    "message": {
                        "type": "string",
                        "description": "The notification message to send (plain text)"
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject line (only used for email channel)"
                    },
                    "to": {
                        "type": "string",
                        "description": "Recipient email address (only for email channel)"
                    },
                    "url": {
                        "type": "string",
                        "description": "Webhook URL to POST to (only for webhook channel)"
                    },
                    "payload": {
                        "type": "object",
                        "description": "Custom JSON payload for webhook (default: {message: ...})"
                    }
                },
                "required": ["channel", "message"]
            }
        )
