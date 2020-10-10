import threading
import time
import gpiozero


class Spi:

    def __init__(self):
        self.buses = [{"miso": 9, "mosi": 10, "clk": 11, "cs": [8, 7]}]
        self.cshigh = True
        self.max_speed_hz = 500000

    def open(self, bus, cs):
        bus = self.buses[bus]
        self.miso = gpiozero.InputDevice(bus['miso'])
        self.mosi = gpiozero.OutputDevice(bus['mosi'])
        self.clk = gpiozero.OutputDevice(bus['clk'])
        self.cs = gpiozero.OutputDevice(bus['cs'][cs])

    def clk_pulse(self):
        self.clk.on()
        time.sleep(0.5 / self.max_speed_hz)
        self.clk.off()
        time.sleep(0.5 / self.max_speed_hz)

    def send_byte(self, b):
        input = 0
        for _ in range(8):
            input <<= 1
            if b & (1 << 7):
                self.mosi.on()
            else:
                self.mosi.off()

            if self.miso.is_active:
                input |= 1

            self.clk_pulse()
            b <<= 1

        return input

    def set_cs(self, val):
        if self.cshigh:
            if val:
                self.cs.on()
            else:
                self.cs.off()
        else:
            if val:
                self.cs.off()
            else:
                self.cs.on()

    def xfer(self, data):
        o = []
        self.clk.off()
        self.mosi.off()

        self.set_cs(True)
        for b in data:
            o.append(self.send_byte(b))
        self.set_cs(False)

        return o


class Sipo:

    def __init__(self, bus=0, cs=0, speed=100000, n_out=16):
        self.spi = Spi()
        self.spi.open(bus, cs)
        self.spi.max_speed_hz = speed
        self.spi.cshigh = True
        self.n_out = n_out
        self.out_state = [0x00] * (n_out/8)
        self.in_state = self.spi.xfer(list(self.out_state))
        self.lock = threading.RLock()
        self.stopthread = False
        self.input_thread = threading.Thread(target=self.input_loop)
        self.input_thread.daemon = True
        self.input_thread.start()

    def setout(self, out, val):
        i = out / 8
        bit = out % 8
        with self.lock:
            if val:
                self.out_state[i] |= (1 << bit)
            else:
                self.out_state[i] &= ~(1 << bit)
            self.spi.xfer(list(self.out_state))

    def getout(self, out):
        i = out / 8
        bit = out % 8
        with self.lock:
            return (self.out_state[i] & (1 << bit) != 0)

    def getinput(self, inp):
        i = inp / 8
        bit = inp % 8
        with self.lock:
            read = self.spi.xfer(list(self.out_state))
        return (read[i] & (1 << bit) == 0)

    def getcachedinput(self, inp):
        i = inp / 8
        bit = inp % 8
        with self.lock:
            read = list(self.in_state)
            self.in_state[i] |= 1 << bit
        return (read[i] & (1 << bit) == 0)

    def input_loop(self):
        stop = False
        while not stop:
            with self.lock:
                read = self.spi.xfer(list(self.out_state))
                for i, r in enumerate(read):
                    self.in_state[i] &= r
                stop = self.stopthread
            time.sleep(0.1)

    def stop(self):
        with self.lock:
            self.stopthread = True
