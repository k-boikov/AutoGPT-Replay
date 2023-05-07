import json
import os
from datetime import datetime

import openai
from _pytest.monkeypatch import MonkeyPatch
from autogpt.agent.agent import Agent
from autogpt.config.config import Config
from autogpt.llm.token_counter import count_message_tokens, count_string_tokens
from autogpt.logs import TypingConsoleHandler, logger
from colorama import Fore

monkeypatch = MonkeyPatch()


def skip_prompt():
    cfg = Config()
    cfg.skip_reprompt = True


def speed_up_replay():
    def reply_TypingConsoleHandler_emit(emit):
        def new_TypingConsoleHandler_emit(self, record):
            monkeypatch.setattr("random.uniform", lambda a, b: 0)
            emit(self, record)

        return new_TypingConsoleHandler_emit

    TypingConsoleHandler.emit = reply_TypingConsoleHandler_emit(
        TypingConsoleHandler.emit
    )


class MockOpenAI:
    def __init__(self, session_dir, last_session):
        self.current_frame = 1
        self.session_dir = session_dir
        self.last_session = last_session
        self.original_create = openai.ChatCompletion.create

    @staticmethod
    def read_text_file(file):
        with open(
            file,
            "r",
            encoding="utf-8",
        ) as fp:
            return fp.read()

    @staticmethod
    def read_json_file(file):
        with open(
            file,
            "r",
            encoding="utf-8",
        ) as fp:
            return json.load(fp)

    @staticmethod
    def format_response(frame_response, prompt_tokens, model):
        completion_tokens = count_string_tokens(frame_response, model)
        response = {
            "choices": [
                {"message": {"content": frame_response}}  # json.dumps(next_action)
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
        }
        # transform response dict to object using convert_to_openai_object
        return openai.openai_object.OpenAIObject.construct_from(response)

    def mock_start_interaction_loop(self):
        def reply_start_interaction_loop(start_interaction_loop):
            def new_start_interaction_loop(_self):
                _self.created_at = "REPLY_" + datetime.now().strftime("%Y%m%d_%H%M%S")

                monkeypatch.setattr("openai.ChatCompletion.create", self.replay_create)

                start_interaction_loop(_self)

            return new_start_interaction_loop

        Agent.start_interaction_loop = reply_start_interaction_loop(
            Agent.start_interaction_loop
        )

    def replay_create(self, *args, **kwargs):
        frame_folder = os.path.join(
            self.session_dir, self.last_session, str(self.current_frame).zfill(3)
        )
        if not os.path.exists(frame_folder):
            logger.typewriter_log(
                "WARNING:",
                Fore.RED,
                f"Replay frame {self.current_frame} not found! Running live now!",
            )
            return self.original_create(*args, **kwargs)

        messages = kwargs.get("messages")
        model = kwargs.get("model")
        prompt_tokens = count_message_tokens(messages, model)

        if (
            len(messages) > 0
            and 'Respond with: "Acknowledged"' in messages[0]["content"]
        ):
            # No support for Agent responses yet
            return self.original_create(*args, **kwargs)

        next_action_file = None
        summary_file = None
        prompt_summary_file = None

        # walk the frame folder and find the files
        for root, dirs, files in os.walk(frame_folder):
            for file in files:
                if file.endswith("_next_action.json"):
                    next_action_file = file
                elif file.endswith("_summary.txt"):
                    summary_file = file
                elif file.endswith("_prompt_summary.json"):
                    prompt_summary_file = file

        if prompt_summary_file is not None:
            prompt_summary = self.read_json_file(
                os.path.join(frame_folder, prompt_summary_file)
            )

            if prompt_summary == messages:
                if summary_file is not None:
                    # Read text from summary file
                    frame_response = self.read_text_file(
                        os.path.join(frame_folder, summary_file)
                    )
                    return self.format_response(frame_response, prompt_tokens, model)
                else:
                    # No response for summary found
                    return self.original_create(*args, **kwargs)

        # Next action should be the last thing for the frame
        self.current_frame += 1
        if next_action_file is not None:
            # Read json from next action file
            frame_response = self.read_json_file(
                os.path.join(frame_folder, next_action_file)
            )
            return self.format_response(
                json.dumps(frame_response), prompt_tokens, model
            )
        else:
            # No json for next action found
            return self.original_create(*args, **kwargs)
