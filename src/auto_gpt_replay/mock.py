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

from auto_gpt_replay.frame import Frame

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


def log(msg):
    logger.typewriter_log("WARNING:", Fore.RED, msg)


class MockOpenAI:
    def __init__(self, session_dir, last_session):
        self.frames = {}
        self.current_frame = 1
        self.session_dir = session_dir
        self.last_session = last_session
        self.original_create = openai.ChatCompletion.create

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

                monkeypatch.setattr(
                    "openai.ChatCompletion.create", self.replay_ChatCompletion_create
                )

                start_interaction_loop(_self)

            return new_start_interaction_loop

        Agent.start_interaction_loop = reply_start_interaction_loop(
            Agent.start_interaction_loop
        )

    def replay_ChatCompletion_create(self, *args, **kwargs):
        messages = kwargs.get("messages")
        model = kwargs.get("model")

        current_frame = self._get_frame()

        replay = current_frame.try_replay(messages, model)
        if replay is False:
            return self.original_create(*args, **kwargs)

        if current_frame.is_end_of_frame:
            self.current_frame += 1

        prompt_tokens = count_message_tokens(messages, model)
        return self.format_response(replay, prompt_tokens, model)

    def _get_frame(self):
        # check if frame exists

        if self.current_frame not in self.frames:
            # if not, create it
            self.frames[self.current_frame] = Frame(
                self.current_frame,
                self.session_dir,
                self.last_session,
                log,
            )

        # Remove old frames if exists
        if self.current_frame - 1 in self.frames:
            del self.frames[self.current_frame - 1]

        return self.frames[self.current_frame]
