import socket
import struct
import json
import time

def pack_varint(d):
    """Encode an integer as a Minecraft VarInt (unsigned 32-bit base-128).

    The previous implementation used `iter(lambda: d >> 7, 0)`, where the
    lambda always returned the *same* value (it never advanced `d`). For any
    value >= 128 (e.g. the -1 protocol version = 0xFFFFFFFF) the sentinel 0 was
    never reached, so the generator ran forever and `b''.join` accumulated
    bytes until the backend ran out of memory (~25-45 MB/s). This is triggered
    by the Server List Ping query, i.e. as soon as the server is online.
    """
    d &= 0xFFFFFFFF
    out = bytearray()
    while True:
        byte = d & 0x7F
        d >>= 7
        if d:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            break
    return bytes(out)

def get_server_status(host='127.0.0.1', port=25565, timeout=0.6):
    """
    Queries valid Minecraft Server List Ping (1.7+)
    Returns: dict with 'players': {'online': int, 'max': int, 'sample': []}, 'version': str, 'motd': str
    """
    sock = None
    try:
        # Connect
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))

        # Handshake Packet
        # ID=0x00, Protocol Version=-1 (varint), Host (string), Port (unsigned short), Next State=1 (status)
        host_bytes = host.encode('utf-8')
        handshake_data = b'\x00' + pack_varint(-1 & 0xFFFFFFFF) + pack_varint(len(host_bytes)) + host_bytes + struct.pack('>H', port) + pack_varint(1)
        
        # Send Handshake
        sock.sendall(pack_varint(len(handshake_data)) + handshake_data)

        # Status Request Packet
        # ID=0x00
        sock.sendall(pack_varint(1) + b'\x00')

        # Read Response
        # Length (varint)
        # Packet ID (varint, should be 0x00)
        # JSON Length (varint)
        # JSON String
        
        # Simple reader helper
        def read_varint(s):
            val = 0
            shift = 0
            while True:
                b = s.recv(1)
                if not b: raise Exception("Connection closed")
                byte = ord(b)
                val |= (byte & 0x7F) << shift
                if not (byte & 0x80):
                    return val
                shift += 7
                # A valid Varint is at most 5 bytes (32-bit). Guard against a
                # malicious/broken server sending endless continuation bytes.
                if shift >= 35:
                    raise Exception("Varint too large")

        _length = read_varint(sock)
        _packet_id = read_varint(sock)
        json_length = read_varint(sock)

        # Cap the JSON payload we are willing to buffer. A real Server List Ping
        # response is a few KB; anything bigger means something is wrong and we
        # must not grow `json_str` unboundedly in memory.
        MAX_JSON_LENGTH = 1_048_576  # 1 MB
        if json_length > MAX_JSON_LENGTH:
            raise Exception(f"Status JSON too large: {json_length}")

        json_str = b""
        while len(json_str) < json_length:
            chunk = sock.recv(json_length - len(json_str))
            if not chunk: break
            json_str += chunk

        data = json.loads(json_str.decode('utf-8'))

        return {
            "online": True,
            "players": {
                "online": data.get('players', {}).get('online', 0),
                "max": data.get('players', {}).get('max', 0),
                "sample": data.get('players', {}).get('sample', [])
            },
            "version": data.get('version', {}).get('name', 'Unknown'),
            "motd": data.get('description', {}).get('text', '') if isinstance(data.get('description'), dict) else str(data.get('description', ''))
        }

    except Exception:
        return {"online": False, "players": {"online": 0, "max": 0, "sample": []}}
    finally:
        try:
            if sock is not None:
                sock.close()
        except Exception:
            pass
