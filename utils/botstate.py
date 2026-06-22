import asyncio

class Botstate:
    def __init__(self):
        self.graid_queue = asyncio.Queue()
        self.cache = {}