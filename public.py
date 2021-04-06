# -*- coding: utf-8 -*-
from myupdate import EFT
import time
import settings_username

def work():
	a=EFT(settings_username)
	a.update()
	a.gamestart()
	a.setprofile(True)
	#a.exportText()
	#a.cacheprices()
	while(1):
		#a.gosnipe()
		#a.goshopping('Jaeger')
		a.goshopping('Therapist')
		#a.goshopping('Mechanic')

if __name__ == "__main__":
	while(1):
		work()
		time.sleep(60)