import SocketServer
import inspect
import sipo
import time
from optparse import OptionParser
import threading
import struct
import logging
import ina226_driver_aardvark as ina226

def readv(res):
    # This is needed because sometimes voltage channels get swapped:
    # Read the same channel multiple times in order to be sure to get the actual 
    # channel and not the other.
    l = 8
    v = []

    for i in range(l):
        with open(res) as volt:
            try:
                v.append(int(volt.read()))
            except Exception, e:
                logging.error("%s %s" % (res, str(e)))
                return None

    # Use only the last 3 readings, drop the lowest and highest
    # which may be outliers
    v = v[-3:]

    v.sort()
    m = v[0]
    out = v[1]
    M = v[2]

    if abs(out - m) > 3 or abs(out - M) > 3:
        logging.debug("%s out %d min %d, max %d\n" % (res, out, m, M))
    return out

class CmdTCPHandler(SocketServer.StreamRequestHandler):

    def handle(self):
        # self.request is the TCP socket connected to the client
        while True:
            line = self.rfile.readline()
            if line == "":
                return
            data = line.strip().split()
            if len(data) > 0:
                cmd = data[0]
                for command in inspect.getmembers(self, predicate=inspect.ismethod):
                    if command[0] == "cmd_" + cmd:
                        ret = command[1](data)
                        if ret == None:
                            return
                        elif ret[0] == 0:
                            self.request.sendall("0 Command OK.%s%s\n" % ("\n" if len(ret) > 1 else "", "\n".join(ret[1:])))
                        elif ret[0] == -2:
                            self.request.sendall("-2 Invalid arguments.\n")
                        else:
                            self.request.sendall("%d Error.%s\n" % "\n".join(ret[1:]))
                        break
                else:
                    self.request.sendall("-1 Command not found.\n")
                #self.request.sendall("\n")

    def cmd_pulseoutcond(self, args):
        try:
            out = int(args[1])
            val = int(args[2])
            delay = int(args[3])
            cond = int(args[4])
        except:
            return [-2]

        inp = self.server.sipo.getinput(cond)
        if bool(val) != bool(inp):
            return self.cmd_pulseout(["", out, 1, delay])
        return [0]

    def cmd_pulseout(self, args):
        try:
            out = int(args[1])
            val = int(args[2])
            delay = int(args[3])
        except:
            return [-2]

        self.server.sipo.setout(out, val)
        time.sleep(delay/1000.0)
        self.server.sipo.setout(out, not val)
        return [0]

    def cmd_setout(self, args):
        try:
            out = int(args[1])
            val = int(args[2])
        except:
            return [-2]

        self.server.sipo.setout(out, val)
        return [0]

    def cmd_getout(self, args):
        try:
            out = int(args[1])
        except:
            return [-2]

        val = self.server.sipo.getout(out)
        ret = [0]
        ret.append("1" if val else "0")
        return ret

    def cmd_getin(self, args):
        try:
            inp = int(args[1])
        except:
            return [-2]

        val = self.server.sipo.getinput(inp)
        ret = [0]
        ret.append("1" if val else "0")
        return ret

    def cmd_getcachedin(self, args):
        try:
            inp = int(args[1])
        except:
            return [-2]

        val = self.server.sipo.getcachedinput(inp)
        ret = [0]
        ret.append("1" if val else "0")
        return ret


    def cmd_getvolt(self, args):
        try:
            res = args[1]
            scale = float(args[2])
            offset = float(args[3])
        except:
            return [-2]

        with self.server.powerlock:
            v = readv(res)

        if v == None:
            return [-2]

        vout = v  * scale
        vout += offset
        ret = [0]
        ret.append("%.01f" % vout)
        return ret

    def cmd_getcurrent(self, args):
        try:
            res = args[1]
            scale = float(args[2])
            offset = float(args[3])
        except:
            return [-2]

        with self.server.powerlock:
            with open(res, "rb") as curr:
                try:
                    page = curr.read()
                    i = struct.unpack('<BhhhB', page)[3]
                except Exception, e:
                    logging.error("%s %s" % (res, str(e)))
                    return [-2]

        i *= scale
        i += offset
        ret = [0]
        ret.append("%.02f" % i)
        return ret
    
    def cmd_read_ina(self, args):
        try:
            i2cbus = int(args[1])
            address = int(args[2], 16)
            shunt = float(args[3])
            imax =  float(args[4])
            volt_curr = args[5]

            sensor = ina226.ina226(address, i2cbus)
            sensor.configure(avg = ina226.ina226_averages_t['INA226_AVERAGES_64'],)
            sensor.calibrate(rShuntValue = shunt, iMaxExcepted = imax)  
        except:
            return [-2]

        ret = [0]
        val = 0
        if volt_curr.startswith("curr"):
            val = sensor.readShuntCurrent()
        else:
            val = sensor.readBusVoltage()
        ret.append("%.02f" % val)
        return ret


        


    def cmd_quit(self, args):
        self.request.sendall("0 Bye Bye!\n")

class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    allow_reuse_address = True

if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("--port", dest="port",
                  help="Server port", type="int", default=8023)
    parser.add_option("--spibus", dest="bus",
                  help="SPI bus to use", type="int", default=0)
    parser.add_option("--spics", dest="cs",
                  help="SPI CS signal to use", type="int", default=0)
    parser.add_option("--spispeed", dest="speed",
                  help="SPI frequency", type="int", default=100000)
 
    (options, args) = parser.parse_args()
    HOST, PORT = "0.0.0.0", options.port
    # Create the server
    server = ThreadedTCPServer((HOST, PORT), CmdTCPHandler)
    server.sipo = sipo.Sipo(options.bus, options.cs, options.speed)
    server.powerlock = threading.RLock()

    server_thread = threading.Thread(target=server.serve_forever)
    logging.basicConfig(level=logging.DEBUG)
    logging.info("BattCaverna I/O started")
    server_thread.start()

