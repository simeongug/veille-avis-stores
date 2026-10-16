import os
import smtplib
from email.message import EmailMessage


def send(subject, html, text, to, dry_run=False, label="mail"):
    if dry_run:
        os.makedirs("out", exist_ok=True)
        with open(f"out/{label}.html", "w", encoding="utf-8") as f:
            f.write(html)
        with open(f"out/{label}.txt", "w", encoding="utf-8") as f:
            f.write(f"Objet : {subject}\nÀ : {', '.join(to)}\n\n{text}\n")
        print(f"[dry-run] {subject} -> out/{label}.html")
        return
    host, user, pwd = os.environ["SMTP_HOST"], os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    msg = EmailMessage()
    msg["Subject"], msg["To"] = subject, ", ".join(to)
    msg["From"] = os.environ.get("MAIL_FROM", user)
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=30) as s:
            s.login(user, pwd)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls()
            s.login(user, pwd)
            s.send_message(msg)
    print(f"Email envoyé à {msg['To']} : {subject}")
