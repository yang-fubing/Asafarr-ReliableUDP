import binascii
import pickle

# Assumes last field is the checksum!
def validate_checksum(message):
    try:
        msg,reported_checksum = message.rsplit('|',1)
        msg += '|'
        return generate_checksum(msg) == reported_checksum
    except:
        return False

# Assumes message does NOT contain final checksum field. Message MUST end
# with a trailing '|' character.
def generate_checksum(message):
    return str(binascii.crc32(message.encode()) & 0xffffffff)

# 使用 bytes 对传递信息进行编码时，需要重写 checksum 功能。
# 验证 checksum 
def validate_checksum_bytes(message):
    try:
        msg_package = pickle.loads(message)
        checksum = msg_package["checksum"]
        del msg_package["checksum"]
        return generate_checksum_bytes(pickle.dumps(msg_package)) == checksum
    except Exception as e:
        return False

# 修改
def generate_checksum_bytes(message):
    return str(binascii.crc32(message) & 0xffffffff)
