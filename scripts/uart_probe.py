"""Send the AmebaD ROM 'read register' probe (read-only) and dump any raw reply."""
import sys, time, struct, serial
s = serial.Serial(); s.port = sys.argv[1]; s.baudrate = int(sys.argv[2]); s.timeout = 0.2
s.dtr = False; s.rts = False; s.open()
time.sleep(0.2); pre = s.read(4096)
print("before:", pre.hex(" ") or "-")
for i in range(3):
    s.write(struct.pack("<BI", 0x31, 0x82000)); time.sleep(0.5)
    print("reply:", s.read(4096).hex(" ") or "-")
s.close()
