"""
Email Dispatch Utilities with AWS SES SMTP Integration.
Handles OTP delivery, trial onboarding credential delivery, and administrative alerts.
"""

import os
import csv
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger("email_utils")

# Default sender identity verified in AWS SES
DEFAULT_SENDER_EMAIL = os.getenv("SMTP_FROM_EMAIL", "noreply@curiosityhub.co.in")
DEFAULT_SENDER_NAME = os.getenv("SMTP_FROM_NAME", "Curiosity HUB")

_SMTP_CACHE: Optional[Dict[str, Any]] = None


def get_smtp_config() -> Optional[Dict[str, Any]]:
    """Loads and caches AWS SES SMTP credentials from smtp-credentials.csv or environment variables."""
    global _SMTP_CACHE
    if _SMTP_CACHE is not None:
        return _SMTP_CACHE

    # 1. Check environment variables
    env_host = os.getenv("SMTP_HOST") or os.getenv("AWS_SES_SMTP_HOST")
    if env_host:
        _SMTP_CACHE = {
            "host": env_host,
            "port": int(os.getenv("SMTP_PORT", 587)),
            "username": os.getenv("SMTP_USER") or os.getenv("AWS_SES_SMTP_USER", ""),
            "password": os.getenv("SMTP_PASS") or os.getenv("AWS_SES_SMTP_PASS", ""),
            "from_email": os.getenv("SMTP_FROM_EMAIL", DEFAULT_SENDER_EMAIL),
            "from_name": os.getenv("SMTP_FROM_NAME", DEFAULT_SENDER_NAME),
        }
        return _SMTP_CACHE

    # 2. Look for smtp-credentials.csv in known paths
    candidate_paths = [
        Path("smtp-credentials.csv"),
        Path(__file__).resolve().parent.parent.parent / "smtp-credentials.csv",
        Path("D:/Attendance System/smtp-credentials.csv"),
    ]

    for p in candidate_paths:
        if p.exists():
            try:
                with open(p, mode="r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    row = next(reader)
                    _SMTP_CACHE = {
                        "host": row.get("SMTP Endpoint", "").strip(),
                        "port": int(row.get("Port", 587)),
                        "username": row.get("Username", "").strip(),
                        "password": row.get("Password", "").strip(),
                        "from_email": DEFAULT_SENDER_EMAIL,
                        "from_name": DEFAULT_SENDER_NAME,
                    }
                    logger.info(f"Loaded AWS SES SMTP credentials from {p}.")
                    return _SMTP_CACHE
            except Exception as e:
                logger.error(f"Error reading SMTP credentials from {p}: {e}")

    logger.warning("No SMTP configuration found. Emails will be logged to console in mock mode.")
    return None


def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None,
) -> bool:
    """Dispatches a MIME email via AWS SES SMTP with STARTTLS."""
    config = get_smtp_config()
    if not config or not config.get("host"):
        logger.info(f"[MOCK EMAIL] To: {to_email} | Subject: {subject}\n{text_content or html_content}")
        return True

    from_addr = f"{config['from_name']} <{config['from_email']}>"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_email

    if text_content:
        msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        server = smtplib.SMTP(config["host"], config["port"], timeout=15)
        server.starttls()
        server.login(config["username"], config["password"])
        server.send_message(msg)
        server.quit()
        logger.info(f"Email successfully delivered to '{to_email}' with subject '{subject}'.")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to '{to_email}' via AWS SES SMTP: {e}", exc_info=True)
        return False


def send_otp_email(to_email: str, recipient_name: str, otp_code: str) -> bool:
    """Sends a 6-digit OTP verification email to the user for self-service demo registration."""
    subject = f"{otp_code} is your Curiosity HUB Free Demo Verification Code"

    name_display = recipient_name.strip() if recipient_name else "there"

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{subject}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 0; background-color: #f1f5f9; color: #1e293b; }}
    .email-container {{ max-width: 560px; margin: 30px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.06); border: 1px solid #e2e8f0; }}
    .email-header {{ background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%); padding: 32px 28px; text-align: center; color: #ffffff; }}
    .email-header h1 {{ margin: 0; font-size: 22px; font-weight: 800; letter-spacing: -0.5px; }}
    .email-header p {{ margin: 6px 0 0; font-size: 13px; color: #94a3b8; letter-spacing: 0.5px; text-transform: uppercase; }}
    .email-body {{ padding: 36px 32px; }}
    .greeting {{ font-size: 16px; font-weight: 600; color: #0f172a; margin-bottom: 12px; }}
    .message-text {{ font-size: 14.5px; line-height: 1.6; color: #475569; margin: 0 0 24px; }}
    .otp-box {{ background: #f8fafc; border: 2px dashed #cbd5e1; border-radius: 10px; padding: 20px; text-align: center; margin: 24px 0; }}
    .otp-label {{ font-size: 12px; font-weight: 700; text-transform: uppercase; color: #64748b; letter-spacing: 1px; margin-bottom: 8px; }}
    .otp-code {{ font-family: 'Courier New', Courier, monospace; font-size: 34px; font-weight: 800; letter-spacing: 8px; color: #2563eb; margin: 0; }}
    .otp-expiry {{ font-size: 12px; color: #94a3b8; margin-top: 8px; }}
    .security-note {{ font-size: 12.5px; color: #64748b; line-height: 1.5; padding: 14px; background: #f8fafc; border-left: 3px solid #f59e0b; border-radius: 0 8px 8px 0; margin-top: 24px; }}
    .email-footer {{ padding: 24px; text-align: center; background: #f8fafc; border-top: 1px solid #e2e8f0; font-size: 12px; color: #94a3b8; }}
    .email-footer a {{ color: #2563eb; text-decoration: none; }}
  </style>
</head>
<body>
  <div class="email-container">
    <div class="email-header">
      <h1>Curiosity HUB</h1>
      <p>Face Recognition Employee Management SaaS</p>
    </div>
    <div class="email-body">
      <div class="greeting">Hello {name_display},</div>
      <p class="message-text">
        Thank you for requesting access to the <strong>Curiosity HUB Free Demo</strong>. Please use the following 6-digit verification code to confirm your email and launch your 7-day Pro Edition trial portal:
      </p>
      <div class="otp-box">
        <div class="otp-label">Verification Code (OTP)</div>
        <div class="otp-code">{otp_code}</div>
        <div class="otp-expiry">Valid for 10 minutes &bull; Single-use only</div>
      </div>
      <div class="security-note">
        <strong>Security Tip:</strong> Never share this verification code with anyone. Curiosity HUB support team will never ask for your code. If you did not request this demo, you can safely ignore this email.
      </div>
    </div>
    <div class="email-footer">
      &copy; 2026 Curiosity HUB. Ahmedabad, Gujarat, India.<br>
      Automated workforce management &bull; Zero hardware Capex<br>
      <a href="https://curiosityhub.co.in">curiosityhub.co.in</a>
    </div>
  </div>
</body>
</html>
"""

    text = f"""Hello {name_display},

Your Curiosity HUB Free Demo verification code is: {otp_code}

This code is valid for 10 minutes. Enter it on the website to instantly activate your 7-day Pro Edition trial.

If you did not request this code, please ignore this email.

Curiosity HUB
https://curiosityhub.co.in
"""

    return send_email(to_email, subject, html, text)


def send_demo_welcome_email(
    to_email: str,
    recipient_name: str,
    company_name: str,
    portal_url: str,
    username: str,
    password: str,
    expires_at_str: str,
) -> bool:
    """Dispatches onboarding welcome email with direct portal link and admin credentials."""
    subject = f"Welcome to Curiosity HUB! Your Free Demo Portal is Ready — {company_name}"

    name_display = recipient_name.strip() if recipient_name else "Administrator"

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{subject}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 0; background-color: #f1f5f9; color: #1e293b; }}
    .email-container {{ max-width: 600px; margin: 30px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.06); border: 1px solid #e2e8f0; }}
    .email-header {{ background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%); padding: 36px 32px; text-align: center; color: #ffffff; }}
    .email-header h1 {{ margin: 0; font-size: 24px; font-weight: 800; letter-spacing: -0.5px; }}
    .email-header p {{ margin: 6px 0 0; font-size: 13px; color: #94a3b8; letter-spacing: 0.5px; text-transform: uppercase; }}
    .email-body {{ padding: 36px 32px; }}
    .greeting {{ font-size: 17px; font-weight: 700; color: #0f172a; margin-bottom: 12px; }}
    .message-text {{ font-size: 14.5px; line-height: 1.6; color: #475569; margin: 0 0 20px; }}
    .credentials-card {{ background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 10px; padding: 20px; margin: 24px 0; }}
    .card-title {{ font-size: 13px; font-weight: 700; text-transform: uppercase; color: #2563eb; letter-spacing: 0.5px; margin-bottom: 14px; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px; }}
    .credential-row {{ display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 14px; }}
    .cred-label {{ color: #64748b; font-weight: 500; }}
    .cred-value {{ color: #0f172a; font-weight: 700; font-family: 'Courier New', Courier, monospace; }}
    .cta-btn-wrapper {{ text-align: center; margin: 28px 0; }}
    .cta-btn {{ display: inline-block; background: #2563eb; color: #ffffff !important; padding: 14px 32px; border-radius: 8px; font-weight: 700; font-size: 15px; text-decoration: none; box-shadow: 0 4px 14px rgba(37, 99, 235, 0.3); }}
    .features-list {{ margin: 24px 0; padding-left: 20px; font-size: 13.5px; color: #475569; line-height: 1.8; }}
    .features-list li strong {{ color: #0f172a; }}
    .expiry-alert {{ background: #fef3c7; border-left: 4px solid #f59e0b; padding: 12px 16px; border-radius: 0 8px 8px 0; font-size: 13px; color: #92400e; margin-top: 24px; }}
    .email-footer {{ padding: 24px; text-align: center; background: #f8fafc; border-top: 1px solid #e2e8f0; font-size: 12px; color: #94a3b8; }}
    .email-footer a {{ color: #2563eb; text-decoration: none; }}
  </style>
</head>
<body>
  <div class="email-container">
    <div class="email-header">
      <h1>Curiosity HUB</h1>
      <p>Face Recognition Employee Management SaaS</p>
    </div>
    <div class="email-body">
      <div class="greeting">Welcome aboard, {name_display}!</div>
      <p class="message-text">
        Your 7-day <strong>Pro Edition</strong> self-service trial portal for <strong>{company_name}</strong> is live and ready for deployment. Your organization has been provisioned with full multi-location biometric attendance, shift scheduling, automated leave management, and Indian statutory payroll.
      </p>

      <div class="credentials-card">
        <div class="card-title">🔐 Your Dedicated Portal Credentials</div>
        <div class="credential-row">
          <span class="cred-label">Portal URL:</span>
          <span class="cred-value"><a href="{portal_url}" style="color: #2563eb; text-decoration: none;">{portal_url}</a></span>
        </div>
        <div class="credential-row">
          <span class="cred-label">Admin Username:</span>
          <span class="cred-value">{username}</span>
        </div>
        <div class="credential-row">
          <span class="cred-label">Temporary Password:</span>
          <span class="cred-value">{password}</span>
        </div>
        <div class="credential-row">
          <span class="cred-label">Plan / Edition:</span>
          <span class="cred-value" style="color: #059669;">PRO Edition (Free Trial)</span>
        </div>
        <div class="credential-row">
          <span class="cred-label">Trial Valid Until:</span>
          <span class="cred-value" style="color: #d97706;">{expires_at_str}</span>
        </div>
      </div>

      <div class="cta-btn-wrapper">
        <a href="{portal_url}" class="cta-btn">🚀 Open Your Admin Dashboard</a>
      </div>

      <p class="message-text" style="font-weight: 600; margin-bottom: 8px;">Quick-Start Guide (Get Running in 3 Minutes):</p>
      <ul class="features-list">
        <li><strong>Step 1:</strong> Log in and navigate to <strong>Employees</strong> &rarr; <em>Register Employee</em> to enroll your team via webcam or smartphone.</li>
        <li><strong>Step 2:</strong> Open the <strong>Dashboard Camera</strong> or launch a tablet kiosk to start live facial biometric attendance.</li>
        <li><strong>Step 3:</strong> Configure <strong>Shifts</strong>, <strong>Leaves</strong>, and <strong>Salary Structures</strong> in Organization Settings.</li>
      </ul>

      <div class="expiry-alert">
        <strong>Trial Notice:</strong> This complimentary demo is active for exactly 7 days until <strong>{expires_at_str}</strong>. To upgrade to an annual plan or request assistance, contact us at <a href="mailto:curiosityhubahd@gmail.com" style="color: #92400e;">curiosityhubahd@gmail.com</a> or <strong>+91-8866868245</strong>.
      </div>
    </div>
    <div class="email-footer">
      &copy; 2026 Curiosity HUB. Ahmedabad, Gujarat, India.<br>
      High-precision biometric attendance &bull; Zero hardware requirement<br>
      <a href="https://curiosityhub.co.in">curiosityhub.co.in</a>
    </div>
  </div>
</body>
</html>
"""

    text = f"""Welcome aboard, {name_display}!

Your 7-day Pro Edition demo portal for {company_name} is active and ready:

Portal URL: {portal_url}
Admin Username: {username}
Temporary Password: {password}
Plan: Pro Edition (7-Day Trial)
Trial Valid Until: {expires_at_str}

Log in now to enroll employees and experience zero-hardware facial recognition attendance:
{portal_url}

Need help or wish to upgrade? Contact Curiosity HUB:
Email: curiosityhubahd@gmail.com
Phone: +91-8866868245
Website: https://curiosityhub.co.in
"""

    return send_email(to_email, subject, html, text)
