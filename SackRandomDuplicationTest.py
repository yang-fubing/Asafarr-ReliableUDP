import random, time

from .BasicTest import *

class SackRandomDuplicationTest(BasicTest):
    def handle_packet(self):
        for p in self.forwarder.in_queue:
            if random.choice([True, False]):
                for _ in range(3):
                    self.forwarder.out_queue.append(p)
            else:
                self.forwarder.out_queue.append(p)

        # empty out the in_queue
        self.forwarder.in_queue = []