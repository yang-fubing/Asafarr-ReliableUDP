import random, time

from .BasicTest import *

# 随机延迟
class RandomDelayTest(BasicTest):
    def handle_packet(self):
        for p in self.forwarder.in_queue:
            if random.choice([True, False]):
                time.sleep(0.2)
                self.forwarder.out_queue.append(p)
            else:
                self.forwarder.out_queue.append(p)

        # empty out the in_queue
        self.forwarder.in_queue = []