#! /bin/bash
set -x

install () {
	service=$1.service
	sudo cp ${service} /lib/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable ${service}
	sudo systemctl start ${service}
}

sudo cp battcaverna_io.py /usr/local/bin/
sudo cp sipo.py /usr/local/bin/
sudo cp ina226_driver_aardvark.py /usr/local/bin/
install battcaverna_io
