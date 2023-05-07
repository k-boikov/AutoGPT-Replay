import os
import re
from datetime import datetime
from pathlib import Path


def find_last_session(session_dir):
    if not os.path.exists(session_dir):
        return None

    sessions = os.listdir(session_dir)
    pattern = r"^([0-9]{8})_([0-9]{6})_"
    last_session = None
    last_session_time = datetime(1970, 1, 1, 0, 0, 0)
    for session in sessions:
        match = re.match(pattern, session)
        if match:
            date_str, time_str = match.groups()
            year, month, day = int(date_str[:4]), int(date_str[4:6]), int(date_str[6:])
            hour, minute, second = (
                int(time_str[:2]),
                int(time_str[2:4]),
                int(time_str[4:]),
            )
            dt = datetime(year, month, day, hour, minute, second)
            if dt > last_session_time:
                last_session_time = dt
                last_session = session

    return last_session


def run_replay():
    from autogpt.logs import logger
    from colorama import Fore

    logger.typewriter_log("WARNING:", Fore.RED, "Running in Replay mode")

    session_dir = os.path.join(Path(os.getcwd()), "logs", "DEBUG")
    last_session = find_last_session(session_dir)

    if last_session is None:
        logger.typewriter_log("WARNING:", Fore.RED, "No previous sessions found!")
        return

    logger.typewriter_log("Replaying session:", Fore.GREEN, last_session)

    from auto_gpt_replay.mock import MockOpenAI, skip_prompt, speed_up_replay

    skip_prompt()
    speed_up_replay()

    openai_mock = MockOpenAI(session_dir, last_session)
    openai_mock.mock_start_interaction_loop()
