import json
import os


class Frame:
    session_files = {
        "next_action": "_next_action.json",
        "summary": "_summary.txt",
        "prompt_summary": "_prompt_summary.json",
        "full_message_history": "_full_message_history.json",
        "current_context": "_current_context.json",
        "user_input": "_user_input.txt",
    }

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

    def __init__(self, index, session_dir, session, log, skip_input):
        self.user_input_replayed = False
        self.next_action_replayed = False
        self.summary_replayed = False
        self.index = index
        self.session_dir = session_dir
        self.session = session
        self.frame_folder = os.path.join(
            self.session_dir, self.session, str(self.index).zfill(3)
        )
        if not self._check_frame_exists():
            log(
                f"Replay frame {self.index} not found! Running live now!",
            )
            self.can_replay = False
            return

        self._load_files()
        self.summary_prompt, self.summary = self._load_summary()

        self.current_context = self._load_frame_context()
        # We cannot replay if we don't have a context
        if self.current_context is None:
            self.can_replay = False
            return

        if skip_input:
            self.current_user_input = None
        else:
            self.current_user_input = self._load_user_input()
        self.can_replay = True

    def _check_frame_exists(self):
        return os.path.exists(self.frame_folder)

    def _get_file_content(self, file):
        # check if class has attribute file
        if not hasattr(self, file):
            return None
        file_path = os.path.join(self.frame_folder, getattr(self, file))
        # extract file type from session_files
        file_type = self.session_files[file].split(".")[-1]
        if file_type == "json":
            return self.read_json_file(file_path)
        return self.read_text_file(file_path)

    def _load_files(self):
        # walk the frame folder and find the files
        for root, dirs, files in os.walk(self.frame_folder):
            for file in files:
                for key, value in self.session_files.items():
                    if file.endswith(value):
                        setattr(self, key, file)

    def try_replay_message(self, messages):
        if not self.can_replay:
            return False

        if len(messages) == 0:
            # What is this?
            return False

        if self.summary_replayed is False and messages == self.summary_prompt:
            self.summary_replayed = True
            return self.summary

        if self._get_last_context_message() == messages[-1]:
            self.next_action_replayed = True
            next_action = self._get_next_action()
            if next_action is None:
                return False
            return next_action

        return False

    def try_replay_input(self):
        if not self.can_replay:
            return False

        if self.current_user_input is not None:
            self.user_input_replayed = True
            return self.current_user_input

        return False

    def is_end_of_frame(self):
        if self.current_user_input is not None and self.user_input_replayed is False:
            return False
        return self.next_action_replayed

    def _load_frame_context(self):
        frame_context = self._get_file_content("current_context")
        if frame_context is not None and (len(frame_context) < 3):
            return None
        return frame_context

    def _get_last_context_message(self):
        return self.current_context[-1]

    def _load_summary(self):
        summary_prompt = self._get_file_content("prompt_summary")
        if summary_prompt is not None:
            summary = self._get_file_content("summary").strip('"')
        else:
            summary = None
        return summary_prompt, summary

    def _get_next_action(self):
        next_action = self._get_file_content("next_action")
        if next_action is None:
            return None
        return json.dumps(next_action)

    def _load_user_input(self):
        user_input = self._get_file_content("user_input")
        if user_input is None:
            return None
        return user_input.strip('"')
