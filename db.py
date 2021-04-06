# -*- coding: utf-8 -*-
import sqlite3
import time

class Database(object):
	def __init__(self,isLive=True):
		self.sqlite_file='data.db'
		self.isLive=isLive

	def gettable(self):
		return 'prices_live' if self.isLive else 'prices_local'

	def addPrices(self,data):
		conn = sqlite3.connect(self.sqlite_file)
		c = conn.cursor()
		c.executemany("INSERT OR IGNORE INTO %s (id,price,ts) VALUES (?,?,?)"%(self.gettable()),data)
		conn.commit()
		conn.close()

	def updatePrice(self,bid,price):
		conn = sqlite3.connect(self.sqlite_file)
		c = conn.cursor()
		c.execute("UPDATE %s SET price=%s,ts=%s WHERE id='%s'"%(self.gettable(),price,int(time.time()),bid))
		conn.commit()
		conn.close()

	def needupdate(self,bid):
		conn = sqlite3.connect(self.sqlite_file)
		c = conn.cursor()
		c.execute("SELECT ts FROM %s WHERE id ='%s'"%(self.gettable(),bid))
		res = c.fetchone()[0]
		conn.close()
		return int(time.time())>res+86400*5

	def getPrice(self,bid):
		conn = sqlite3.connect(self.sqlite_file)
		c = conn.cursor()
		c.execute("SELECT price FROM %s WHERE id ='%s'"%(self.gettable(),bid))
		res = c.fetchone()[0]
		conn.close()
		return res

if __name__ == '__main__':
	db=Database()
	#db.addPrices(set([(x,prices_live.data[x],int(time.time())) for x in prices_live.data]))
	print(db.getPrice('5644bd2b4bdc2d3b4c8b4572'))
	print(db.needupdate('5644bd2b4bdc2d3b4c8b4572'))