import logging
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart

import aiosmtplib

from ..config import Settings
from .constants import SDI_PEC

logger = logging.getLogger(__name__)


async def send_via_pec(xml_bytes: bytes, filename: str, settings: Settings) -> None:
    msg = MIMEMultipart()
    msg["From"] = settings.pec_user
    msg["To"] = SDI_PEC
    msg["Subject"] = ""

    attachment = MIMEBase("application", "xml")
    attachment.set_payload(xml_bytes)
    encoders.encode_base64(attachment)
    attachment.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(attachment)

    await aiosmtplib.send(
        msg,
        hostname=settings.pec_host,
        port=settings.pec_port,
        username=settings.pec_user,
        password=settings.pec_password,
        use_tls=True,
    )
    logger.info("Fattura inviata via PEC al SdI: %s", filename)
