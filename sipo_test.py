#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sipo
import time


spi = sipo.Spi()
spi.open(0, 0)
spi.max_speed_hz = 100000
spi.cshigh = True

off = [0, 0]
on = [0, 64]

while 1:
    i = spi.xfer(list(on))
    print i
    time.sleep(0.3)
    i = spi.xfer(list(off))
    print i
    time.sleep(1)
