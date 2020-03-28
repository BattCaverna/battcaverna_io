import spidev
import threading
import time

class Sipo:
    def __init__(self, bus=0, cs=0, speed=100000, n_out=16):
        self.spi = spidev.SpiDev()
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
    
