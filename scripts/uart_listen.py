"""Read-only UART capture: never writes to the port, keeps DTR/RTS low."""
import sys, time, serial
port, baud, secs, out = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
s = serial.Serial()
s.port, s.baudrate, s.timeout = port, baud, 0.2
s.dtr = False; s.rts = False
s.open()
end = time.time() + secs
with open(out, "wb") as f:
    while time.time() < end:
        d = s.read(4096)
        if d:
            f.write(d); f.flush()
s.close()
