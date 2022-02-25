# Asafarr-ReliableUDP
基于UDP实现可靠传输协议，实现在包丢失、重复、失序等特殊情况下按序、可靠地交付UDP报文段。


我们定义RUDP协议有四种消息类型，分别是start，end，data和ack。start，end，data的消息格式如下：

start|<sequence number>|<data>|<checksum>
  
data|<sequence number>|<data>|<checksum>
  
end|<sequence number>|<data>|<checksum>
  
start消息用来初始化连接，该消息中的sequence number是收发双方使用的初始包序号。发送完start消息后，连接得以建立，接下来便会发送data消息传递数据。
  
end消息用来断开连接，并且，end消息中携带了发送方发给接收方的最后一段数据。
  
本实验实现的发送端能够接收并处理来自接收端的ack消息，ack消息的格式如下：
  
ack|<sequence number>|<checksum>
  
需要注意，我们的RUDP报文的最大长度是有限制的。因为我们模拟以太网下的数据传输，以太网帧最大长度是1518字节，帧头部占18字节，IP头部占20字节，UDP头部占8字节，而我们的RUDP是实现在UDP之上的，因此RUDP报文最大长度是1472字节（包括类型、序列号、数据、校验和）。在实现发送端的代码时，如果待发送的文件过大，则需要将待发送的文件进行分割以“装进”RUDP报文中。
上面所示的协议消息格式中，尖括号（“<”和“>”）不属于消息的一部分，并且注意在“｜”两侧没有空格，在实现发送端代码时需要严格遵循我们规定的这种格式。
