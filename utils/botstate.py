import asyncio

class Botstate:
    def __init__(self):
        self.graid_queue = asyncio.Queue()
        self.war_queue = asyncio.Queue()
        self.cache = {}