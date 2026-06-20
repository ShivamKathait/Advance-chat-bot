
import smtplib
import threading

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings
from app.core.logging import logger_adapter

def _send(to: str, subject: str, html: str, plain: str) -> None:
    """Send an email synchronously. Call via _send_async for non-blocking delivery."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.email_from_name} <{settings.email_from}>"
    msg["To"] = to
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(settings.smtp_username, settings.smtp_password)
        server.sendmail(settings.email_from, to, msg.as_string())


def _send_async(to: str, subject: str, html: str, plain: str) -> None:
    """Fire-and-forget email in a background thread."""
    thread = threading.Thread(
        target=_send_safe,
        args=(to, subject, html, plain),
        daemon=True,
    )
    thread.start()
    
def _send_safe(to: str, subject: str, html: str, plain: str) -> None:
    try:
        _send(to, subject, html, plain)
        logger_adapter.info("Email sent to %s: %s", to, subject)
    except Exception as e:
        logger_adapter.error("Failed to send email to %s: %s", to, str(e))

def send_verification_email(first_name: str, last_name: str, email: str, otp: str) -> None:
    subject = "Verify your email"

    plain = f"""Hello {first_name} {last_name}

    Your verification code is: {otp}
    This code will expire in 10 minutes.
    """
    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; color: #1a1a1a;">
    <p>Hello <strong>{first_name} {last_name}</strong>,</p>
    <p>Use the code below to verify your email address:</p>

    <table style="background:#f5f7fa; border-radius:8px; padding:16px; width:100%; margin:16px 0;">
        <tr>
        <td style="padding:6px 0; text-align:center; font-family:monospace; font-size:28px; letter-spacing:6px;">
            {otp}
        </td>
        </tr>
    </table>

    <p style="color:#e74c3c; font-weight:bold;">
        This code will expire in 10 minutes.
    </p>

    <hr style="border:none; border-top:1px solid #eee; margin:24px 0;">
    <p style="color:#888; font-size:12px;">{settings.email_from_name}</p>
    </body>
    </html>
    """
    _send_async(email, subject, html, plain)