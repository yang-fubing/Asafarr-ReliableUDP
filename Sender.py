"""
在本次试验在 Linux 下使用 python3 完成。
完成了 go-back-N 算法的实现，实现了扩展 selective-acknowledgement 选择重传功能，并使代码可以传输包括视频图文在内的任意格式的文件。

为了处理多种不同格式的文件传输，理想的处理方式应当是使用 bytes 作为编码格式而非 string。原因如下：
1. 直接使用 string 读如非文本文件会产生编码异常，而 bytes 可以完整正确的读入整个文件。
2. string 无法对任意 bytes 进行编码，而 bytes 不仅可以编码任意格式的输入文件，也可以编码几乎任意格式的 python 对象。
但是原始的代码库中硬编码了大量使用 string 的逻辑，尤其是在 TestHarness.py 中，测试代码使用 string 格式进行比较。
出于保持测试代码纯净性的原则，我选择同时保留 string 和 bytes 的处理逻辑。
代码默认使用 string 进行编码，专注于处理文本模式，同时可以通过 TestHarness 测试框架中所有的测试用例（随机延迟，随机丢弃，随机重复，随机重复并乱序，及对应的 Sack 模式）。
当命令行参数 -b 打开时，进入 bytes 模式，具备对任意格式文件的传输功能。

示例：

python Receiver.py &
python Sender.py -f README

python Receiver.py -b &
python Sender.py -f docx.png -b
python Sender.py -f Seoul.mp4 -b
"""
import sys
import time
import getopt
import pickle
import Checksum
import BasicSender


class Message:
    """
    每条待发送的消息
    seqno 表示消息的编号
    msg 表示消息的内容
    timestamp 表示消息上次被发送的时间戳，用于判断是否超时
    """
    def __init__(self, seqno, msg, timestamp):
        self.seqno = seqno
        self.msg = msg
        self.timestamp = timestamp


class Sender(BasicSender.BasicSender):
    def __init__(self, dest, port, filename, debug=False, sackMode=False, bytesMode=False, window_size=5, send_timeout=0.5, receive_timeout=0.05):
        """
        增加额外参数
        window_size 表示滑动窗口大小，默认为 5.
        send_timeout 表示每次发送消息的最长等待时长。超出该时长则都未收到 ACK 则重发。
        receive_timeout 表示每轮发送后接受消息时允许等待的时长。
        正常情况下，在 send_timeout 超时前，滑动窗口内的消息都会被发送过一次，因此不会有消息被饿死。
        """
        super(Sender, self).__init__(dest, port, filename, debug)

        assert window_size > 0
        assert send_timeout > 0
        assert receive_timeout > 0
        self.window_size = window_size
        self.send_timeout = send_timeout
        self.receive_timeout = receive_timeout
        self.sackMode = sackMode
        self.bytesMode = bytesMode

        """
        保持默认的读入接口。如果需要支持多种传输文件类型，则需要对这里进行修改。
        除此之外，下面的编码部分以及 Receiver 相关代码都需要修改。
        """
        if filename == None:
            self.infile = sys.stdin
        elif self.bytesMode:
            self.infile = open(filename,"rb")
        else:
            self.infile = open(filename,"r")

    # Handles a response from the receiver.
    """
    检查 checksum 是否有错。目前没有进行校验。
    这里可以加一个如果 checksum 错误就忽视掉这条消息的代码。
    """
    def handle_response(self,response_packet):
        if Checksum.validate_checksum(response_packet):
            print("recv: %s" % response_packet) 
            return True
        else:
            print("recv: %s <--- CHECKSUM FAILED" % response_packet)
            return False

    # 重载 make_packet 函数，使用 pickle 进行 serialize 
    def make_packet_bytes(self, msg_type, seqno, msg):
        msg_package = {'msg_type': msg_type, 'seqno': seqno, 'msg': msg}
        checksum = Checksum.generate_checksum_bytes(pickle.dumps(msg_package))
        msg_package['checksum'] = checksum
        return pickle.dumps(msg_package)

    # 重载 split_packet 函数
    def split_packet_bytes(self, message):
        msg_package = pickle.loads(message)
        msg_type = msg_package["msg_type"]
        seqno = msg_package["seqno"]
        msg = msg_package["msg"]
        checksum = msg_package["checksum"]
        return msg_type, seqno, msg, checksum

    # 重载 send 函数
    def send_bytes(self, message, address=None):
        if address is None:
            address = (self.dest,self.dport)
        self.sock.sendto(message, address)

    # Main sending loop.
    def start(self):
        """
        offset 表示在当前滑动窗口中即将发送第几条消息。
        msg 表示当前滑动窗口。
        next_seqno 和 next_msg 表示下一条待发送的消息。
        默认每次读取 500 字节。开到 1000 字节也可以正常运行。
        这里为了 debug 方便，选择了较小的读入大小，可以产生更多的消息数量。
        """
        offset = 0
        msg = []
        next_seqno = 0
        next_msg = self.infile.read(500)
        
        """
        如果消息还未发送完，则需要继续处理
        """
        while (next_msg != "" and next_msg != b"") or len(msg) > 0:
            if len(msg) > 0 and time.time() - msg[0].timestamp >= self.send_timeout:
                """
                如果滑动窗口最早的消息超时了，那么重置到最早的这条消息。
                """
                offset = 0
            elif (len(msg) == 0 or next_seqno - msg[0].seqno < self.window_size) and len(msg) < self.window_size and (next_msg != "" and next_msg != b""):
                """
                满足下列条件，则往滑动窗口中加新的信息：
                1. 新信息的编号与滑动窗口中最早的信息相差不超过窗口大小（，否则这条新加入的信息会超过 Recevier 中滑动窗口的大小，会被直接抛弃，没有意义）
                2. 滑动窗口未满
                3. 还有可加的新信息
                """
                msg.append(Message(next_seqno, next_msg, 0.0))
                next_seqno += 1
                next_msg = self.infile.read(500)
            
            if offset < len(msg):
                """
                如果滑动窗口中还有待发送的消息，判断其消息类型，组装，并发送。
                """
                msg_type = 'data'
                if msg[offset].seqno == 0:
                    msg_type = 'start'
                elif next_msg == "" and len(msg) == 1:
                    msg_type = 'end'

                if self.bytesMode:
                    packet = self.make_packet_bytes(msg_type, msg[offset].seqno, msg[offset].msg)
                else:
                    packet = self.make_packet(msg_type, msg[offset].seqno, msg[offset].msg)
                msg[offset].timestamp = time.time()
                if self.bytesMode:
                    self.send_bytes(packet)
                else:
                    self.send(packet)
                if self.debug:
                    print("sent seqno: {}".format(msg[offset].seqno))
                offset += 1

            """
            接收新的消息，可以容忍的延迟为 self.receive_timeout 秒。
            注意这里虽然一次只读取一条消息，看上去会很容易产生消息的堆积。
            但是不要紧，在 offset 到达滑动窗口尾部的时候就会停止发送消息的操作，从而集中读取之前未读取的信息。
            """
            response = self.receive(self.receive_timeout)
            if response is not None:
                """
                将读取到的消息解码
                """
                response = response.decode()
                self.handle_response(response)

                ack_seqs = response.strip().split('|')[1].split(';')
                ack_seqno = int(ack_seqs[0])
                if len(ack_seqs) > 1 and len(ack_seqs[1]) > 0:
                    sacks = [int(_) for _ in ack_seqs[1].split(',')]
                else:
                    sacks = []
                if self.debug:
                    print("ack_seqno: ", ack_seqno)
                
                """
                过滤掉滑动窗口中已经被 Receiver 接受的信息。
                在没有开启 sack 选项时，sacks 为空，因此 offset 会被移动到滑动窗口中不小于 ack_seqno 的位置。
                在开启 sack 选项时，还会根据 sacks 数组将滑动窗口中已经被接受的消息过滤。
                最后将 offset 移动到对应的位置。
                """
                offset_seqno = msg[offset].seqno if offset < len(msg) else next_seqno
                msg = [_ for _ in msg if _.seqno >= ack_seqno and _.seqno not in sacks]
                offset = 0
                while offset < len(msg) and msg[offset].seqno < offset_seqno: offset += 1
    
        self.infile.close()
    
    def handle_timeout(self):
        pass

    def handle_new_ack(self, ack):
        pass

    def handle_dup_ack(self, ack):
        pass

    def log(self, msg):
        if self.debug:
            print(msg)


'''
This will be run if you run this script from the command line. You should not
change any of this; the grader may rely on the behavior here to test your
submission.
'''
if __name__ == "__main__":
    def usage():
        print("RUDP Sender")
        print("-f FILE | --file=FILE The file to transfer; if empty reads from STDIN")
        print("-p PORT | --port=PORT The destination port, defaults to 33122")
        print("-a ADDRESS | --address=ADDRESS The receiver address or hostname, defaults to localhost")
        print("-d | --debug Print debug messages")
        print("-h | --help Print this usage message")
        print("-k | --sack Enable selective acknowledgement mode")
        # 额外的参数用于切换 string 读入和 bytes 读入。由于 TestHarness.py 测试框架使用 string 编码信息，因此默认使用 string。
        print("-b | --bytes Using bytes encode message")

    try:
        opts, args = getopt.getopt(sys.argv[1:],
                               "f:p:a:dkb", ["file=", "port=", "address=", "debug=", "sack="])
    except:
        usage()
        exit()

    port = 33122
    dest = "localhost"
    filename = None
    debug = False
    sackMode = False
    bytesMode = False

    for o,a in opts:
        if o in ("-f", "--file="):
            filename = a
        elif o in ("-p", "--port="):
            port = int(a)
        elif o in ("-a", "--address="):
            dest = a
        elif o in ("-d", "--debug="):
            debug = True
        elif o in ("-k", "--sack="):
            sackMode = True
        elif o in ("-b", "--bytes="):
            bytesMode = True

    s = Sender(dest, port, filename, debug, sackMode, bytesMode)
    try:
        s.start()
    except (KeyboardInterrupt, SystemExit):
        exit()
