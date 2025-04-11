import datetime as dt
import logging
import re
from typing import Optional
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TelegramMessage(BaseModel):
    message_id: str
    datetime: Optional[dt.datetime] = None
    text: str

    class Config:
        json_encoders = {dt.datetime: lambda v: v.isoformat() if v else None}


def parse_datetime(date_str: str) -> Optional[dt.datetime]:
    """Parse datetime string with timezone information."""
    try:
        # Extract components from string like "02.01.2025 18:43:24 UTC+03:00"
        match = re.match(
            r"(\d{2}\.\d{2}\.\d{4})\s+(\d{2}:\d{2}:\d{2})\s+UTC([+-]\d{2}):(\d{2})",
            date_str,
        )
        if match:
            date_part, time_part, tz_hours, tz_minutes = match.groups()

            # Parse the local datetime
            local_dt = dt.datetime.strptime(
                f"{date_part} {time_part}", "%d.%m.%Y %H:%M:%S"
            )

            # Create timezone offset
            tz_offset = (
                int(tz_hours) * 3600 + int(tz_minutes) * 60
            )  # Convert to seconds
            timezone = ZoneInfo("UTC")

            # Convert to UTC
            utc_dt = local_dt.replace(
                tzinfo=ZoneInfo(f"Etc/GMT{-int(tz_hours):+d}")
            ).astimezone(timezone)

            return utc_dt
    except (ValueError, TypeError):
        pass
    return None


def parse_telegram_messages(html_content: str) -> list[TelegramMessage]:
    soup = BeautifulSoup(html_content, "lxml")
    messages = []

    # Find all message divs (both default and service messages)
    message_divs = soup.find_all(
        "div", class_=["message default clearfix", "message service"]
    )

    for message in message_divs:
        # Get message ID
        message_id = message.get("id")

        # Get datetime
        date_div = message.find("div", class_="pull_right date details")
        message_datetime = None
        if date_div:
            date_str = date_div.get("title", "")
            if date_str:
                message_datetime = parse_datetime(date_str)

        # Get text content
        text_div = message.find("div", class_="text")
        logger.debug(f"Text content: {text_div}")
        if text_div:
            text_div_html = str(text_div)
            text_div_html = re.sub(r"<br\s*/>", "\n", text_div_html)
            text_content = BeautifulSoup(text_div_html, "lxml").text
            # text_content = text_div_soup.(strip=False)
            # text_content = str(text_div)
        else:
            # For service messages (dates)
            body_details = message.find("div", class_="body details")
            if body_details:
                text_content = body_details.get_text(strip=True)
            else:
                text_content = ""

        # Create TelegramMessage instance
        telegram_message = TelegramMessage(
            message_id=message_id, datetime=message_datetime, text=text_content
        )
        messages.append(telegram_message)

    return messages


def main():
    import argparse

    from ..config.settings import settings

    argparser = argparse.ArgumentParser()
    argparser.add_argument("-d", "--debug", action="store_true")
    args = argparser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)

    data_file = settings.find_file("thedailyton")
    if not data_file:
        logger.error("Data file not found")
        raise ValueError("Data file not found")

    content = data_file.read_text()
    messages = parse_telegram_messages(content)

    for message in messages:
        if args.debug:
            continue

        print("\nMessage ID:", message.message_id)
        print("Datetime:", message.datetime)
        print("Text:", message.text)
        print("-" * 50)


if __name__ == "__main__":
    main()
