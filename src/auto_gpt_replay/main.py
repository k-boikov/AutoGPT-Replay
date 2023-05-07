import os
import re
from datetime import datetime
from pathlib import Path


class Replay:
    def __init__(self):
        self.pattern = r"^([0-9]{8})_([0-9]{6})_"
        self.session_dir = os.path.join(Path(os.getcwd()), "logs", "DEBUG")

    def find_last_session(self):
        if not os.path.exists(self.session_dir):
            return None

        sessions = os.listdir(self.session_dir)

        last_session = None
        last_session_time = datetime(1970, 1, 1, 0, 0, 0)
        for session in sessions:
            match = re.match(self.pattern, session)
            if match:
                date_str, time_str = match.groups()
                year, month, day = (
                    int(date_str[:4]),
                    int(date_str[4:6]),
                    int(date_str[6:]),
                )
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

    def run_replay(self):
        from autogpt.logs import logger
        from colorama import Fore

        logger.typewriter_log("WARNING:", Fore.RED, "Running in Replay mode")

        last_session = self.find_last_session()

        if last_session is None:
            logger.typewriter_log("WARNING:", Fore.RED, "No previous sessions found!")
            return

        while True:
            logger.typewriter_log(
                f"REPLAY found - {last_session}, run?",
                Fore.GREEN,
                "(y / or enter folder name)",
            )
            user_input = input("Input: ")
            if user_input.lower().strip() == "":
                continue
            if user_input.lower().strip() == "y":
                break
            if os.path.exists(os.path.join(self.session_dir, user_input.strip())):
                last_session = user_input
                break
            logger.typewriter_log("REPLAY NOT found, try again...", Fore.RED, "")

        logger.typewriter_log("Replaying session:", Fore.GREEN, last_session)

        from auto_gpt_replay.mock import MockIOFunctions, skip_prompt, speed_up_replay

        skip_prompt()
        speed_up_replay()

        openai_mock = MockIOFunctions(self.session_dir, last_session)
        openai_mock.mock_start_interaction_loop()
