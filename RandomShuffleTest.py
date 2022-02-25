import random

from tests.BasicTest import BasicTest

# 随机重复并打乱。
class RandomShuffleTest(BasicTest):
    def handle_packet(self):
        for p in self.forwarder.in_queue:
            for _ in range(3):
                self.forwarder.out_queue.append(p)
        
        random.shuffle(self.forwarder.out_queue)
        
        # empty out the in_queue
        self.forwarder.in_queue = []
