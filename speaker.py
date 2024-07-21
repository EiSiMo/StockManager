import threading
import pygame
import io
import time
from gtts import gTTS
import logging
import queue

logger = logging.getLogger("Root")


class Speaker(threading.Thread):
    def __init__(self, saying_queue):
        super().__init__()
        self.running = True
        self.saying_queue = saying_queue
        pygame.mixer.init()

    def say(self, text):
        logger.info(f"say({text}) called")
        pygame.mixer.init()
        tts = gTTS(text, lang="de", slow=False)
        logger.debug(f"gTTS audio generated")
        audio_stream = io.BytesIO()
        tts.write_to_fp(audio_stream)
        audio_stream.seek(0)
        pygame.mixer.music.load(audio_stream, "mp3")
        logger.debug(f"playing audio")
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(1)
        logger.debug(f"playing audio completed")

    def run(self):
        while self.running:
            try:
                text = self.saying_queue.get()
                self.say(text)
            except queue.Empty:
                time.sleep(1)
            except Exception as e:
                logger.error("Exception in Speaker thread", exc_info=e)
                self.running = False
