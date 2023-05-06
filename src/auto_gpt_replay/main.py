import json
import os
import re
from datetime import datetime
from pathlib import Path

session_dir = os.path.join(Path(os.getcwd()), "logs", "DEBUG")


def find_last_session():
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

    last_session = find_last_session()

    if last_session is None:
        logger.typewriter_log("WARNING:", Fore.RED, "No previous sessions found!")
        return

    logger.typewriter_log("Replaying session:", Fore.GREEN, last_session)

    from _pytest.monkeypatch import MonkeyPatch

    monkeypatch = MonkeyPatch()

    from autogpt.config.config import Config

    cfg = Config()
    cfg.skip_reprompt = True

    def reply_TypingConsoleHandler_emit(emit):
        def new_TypingConsoleHandler_emit(self, record):
            monkeypatch.setattr("random.uniform", lambda a, b: 0)
            emit(self, record)

        return new_TypingConsoleHandler_emit

    from autogpt.logs import TypingConsoleHandler

    TypingConsoleHandler.emit = reply_TypingConsoleHandler_emit(
        TypingConsoleHandler.emit
    )

    def reply_start_interaction_loop(start_interaction_loop):
        def new_start_interaction_loop(self):
            self.created_at = "REPLY_" + datetime.now().strftime("%Y%m%d_%H%M%S")

            import openai

            current_frame = 1

            def replay_create(*args, **kwargs):
                def format_response(frame_response):
                    response = {
                        "choices": [
                            {
                                "message": {
                                    "content": frame_response  # json.dumps(next_action)
                                }
                            }
                        ],
                        "usage": {
                            "prompt_tokens": 1,
                            "completion_tokens": 1,
                        },
                    }
                    # transform response dict to object using convert_to_openai_object
                    return openai.openai_object.OpenAIObject.construct_from(response)

                nonlocal current_frame
                frame_folder = os.path.join(
                    session_dir, last_session, str(current_frame).zfill(3)
                )
                if not os.path.exists(frame_folder):
                    logger.typewriter_log(
                        "WARNING:",
                        Fore.RED,
                        f"Replay frame {current_frame} not found! Running live now!",
                    )
                    return openai.ChatCompletion.create(*args, **kwargs)

                message = kwargs.get("messages")

                next_action_file = None
                summary_file = None
                prompt_summary_file = None
                # walk the frame folder and search for file containing _next_action.json
                for root, dirs, files in os.walk(frame_folder):
                    for file in files:
                        if file.endswith("_next_action.json"):
                            next_action_file = file
                        elif file.endswith("_summary.txt"):
                            summary_file = file
                        elif file.endswith("_prompt_summary.json"):
                            prompt_summary_file = file

                if prompt_summary_file is not None:
                    with open(
                        os.path.join(frame_folder, prompt_summary_file),
                        "r",
                        encoding="utf-8",
                    ) as fp:
                        prompt_summary = json.load(fp)
                        if prompt_summary == message:
                            if summary_file is not None:
                                with open(
                                    os.path.join(frame_folder, summary_file),
                                    "r",
                                    encoding="utf-8",
                                ) as fp:
                                    # Read text from summary file
                                    frame_response = fp.read()
                                    return format_response(frame_response)
                            else:
                                # No response for summary found
                                return openai.ChatCompletion.create(*args, **kwargs)

                # Next action should be the last thing for the frame
                current_frame += 1
                with open(
                    os.path.join(frame_folder, next_action_file), "r", encoding="utf-8"
                ) as fp:
                    # Read json from next action file
                    frame_response = json.load(fp)
                    return format_response(json.dumps(frame_response))

            monkeypatch.setattr("openai.ChatCompletion.create", replay_create)

            start_interaction_loop(self)

        return new_start_interaction_loop

    from autogpt.agent.agent import Agent

    Agent.start_interaction_loop = reply_start_interaction_loop(
        Agent.start_interaction_loop
    )
