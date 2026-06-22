import logging
import sys
import datetime

def init_logging():
    date = datetime.datetime.now(tz=datetime.timezone.utc)
    filename = date.strftime("bot_log_%Y-%m-%dT%H_%M_%SZ")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(f"logs\\{filename}.log", encoding="utf-8")
        ]
    )

if __name__ == '__main__':
    pass
    #init_logging()
