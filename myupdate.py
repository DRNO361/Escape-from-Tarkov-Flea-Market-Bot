# -*- coding: utf-8 -*-
import eng_live
import eng_local
import io
import json
import random
import requests
import sys
import threading
import time
import vendors
import zlib
from db import Database

from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

class EFT(object):
	def __init__(self,settings={},isLocal=False):
		self.s = requests.Session()
		self.s.verify = False
		p = '127.0.0.1:8888'
		#self.s.proxies.update({'http': 'http://' + p, 'https': 'http://' + p, })
		if settings:
			self.settings = settings
			self.version = self.settings.version
			self.clientversion = self.settings.clientversion
			self.s.headers.update({'Content-Type': 'application/json', 'User-Agent': 'BSG Launcher ' + self.version})
		self.RequestId=0
		self.min_price= 5
		self.sessionid=None
		self.isLocal = isLocal
		self.multiplier = 0.79
		self.db = Database(not isLocal)

	def save(self,data,file):
		with open(file, 'wb') as the_file:
			the_file.write(data.encode())

	def log(self,msg):
		print('[%s] %s'%(time.strftime('%H:%M:%S'),msg))

	def getdata(self, content):
		try:
			content = zlib.decompress(content)
		except:
			content = content
		return json.loads(content)

	def packdata(self,i):
		i=json.dumps(i,separators=(',', ':')).replace(' ', '').replace('\n', '')
		return zlib.compress(i.encode())#.encode()

	def callAPI(self,url,data={}):
		if self.isLocal:
			url='https://localhost'+url.split('.com')[-1]
		ndata = self.packdata(data)
		if 'client/' in url:
			try:
				if 'Authorization' in self.s.headers:
					del self.s.headers['Authorization']
			except:
				pass
			r=self.s.post(url,data=ndata,headers=self.getheader(),cookies={'PHPSESSID':self.sessionid})
		else:
			PHPSESSID=None
			for c in self.s.cookies:
				if c.name=='PHPSESSID':
					PHPSESSID=c.value
			if PHPSESSID:
				r=self.s.post(url,data=ndata,cookies={'PHPSESSID':PHPSESSID})
			else:
				r=self.s.post(url,data=ndata)
		if 'Set-Cookie' in r.headers and 'start' in sys._getframe(1).f_code.co_name:
			self.sessionid=r.headers['Set-Cookie'].split('=')[-1]
			self.log('found new session id:%s'%(self.sessionid))
			self.spawncheck()
		ndata = self.getdata(r.content)
		if ndata['data'] and 'session' in ndata['data']:
			self.sessionid=str(ndata['data']['session'])
			self.log('found new session id:%s'%(self.sessionid))
			self.spawncheck()
		if ndata['err']==214:
			self.log('we have captcha?')
			self.trysolvecaptcha()
			self.log('we have solved captcha!')
			return self.callAPI(url,data)
		if ndata['err']!=0:
			print(ndata,sys._getframe(1).f_code.co_name)
			return None
		return ndata

	def GetLauncherDistrib(self):
		data = self.callAPI('https://launcher.escapefromtarkov.com/launcher/GetLauncherDistrib?launcherVersion=' + self.version)
		if int(data['data']['Version'].split('.')[-1])> int(self.version.split('.')[-1]):
			self.version=str(data['data']['Version'])
			self.log('found launcher version:%s'%(self.version))
		else:
			self.log('our version is higher')
		return data

	def refresh(self):
		data = self.callAPI('https://launcher.escapefromtarkov.com/launcher/token/refresh?launcherVersion='+self.version,{"hwCode":self.settings.hwCode,"grant_type":"refresh_token","client_id":0,"refresh_token":self.settings.refresh_token})
		self.access_token=str(data['data']['access_token'])
		self.settings.refresh_token=str(data['data']['refresh_token'])
		#self.log('found access_token:%s'%(self.access_token))
		return data

	def config(self):
		if 'Authorization' not in self.s.headers:
			self.s.headers.update({'Authorization':self.access_token})
		data = self.callAPI('https://launcher.escapefromtarkov.com/launcher/config?launcherVersion=' + self.version)
		self.nickname=data['data']['nickname']
		self.log('found profile:%s lvl:%s'%(data['data']['nickname'],data['data']['profileLevel']))
		return data

	def GetPatchList(self):
		data = self.callAPI('https://launcher.escapefromtarkov.com/launcher/GetPatchList?launcherVersion=' + self.version + '&branch=live')
		self.clientversion=str(data['data'][0]['Version'])
		self.log('found clientversion:%s'%(self.clientversion))
		return data

	def export(self):
		self.save('refresh_token="%s"\nversion="%s"\nclientversion="%s"\nhwCode="%s"'%(self.settings.refresh_token,self.version,self.clientversion,self.settings.hwCode),'settings_%s.py'%(self.nickname))

	def update(self):
		self.GetLauncherDistrib()
		self.refresh()
		self.config()
		self.GetPatchList()
		self.export()

	def dataCenter(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/launcher/dataCenter/list?launcherVersion=10.4.6.1305&branch=live',data='')
		return data

	def userinfo(self):
		data=self.callAPI('https://www.escapefromtarkov.com/launcher/user/info?branch=live&game_edition=standard&launcher_version=10.4.6.1305&language=en&gameVersion=0.12.9.2.11410',data='')
		return data

	def profileInfo(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/launcher/profileInfo?launcherVersion='+self.version+'&branch=live',data='')
		return data

	def gamestart(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/launcher/game/start?launcherVersion=10.4.6.1305&branch=live',data={"hwCode":self.settings.hwCode,"version":{"major":self.clientversion,"game":"live","backend":"6"}})
		return data

	def getheader(self):
		self.RequestId+=1
		r={'User-Agent':'UnityPlayer/2018.4.28f1 (UnityWebRequest/1.0, libcurl/7.52.0-DEV)','Accept-Encoding':'identity','Content-Type':'application/json','Accept':'application/json','App-Version':'EFT Client '+self.clientversion,'GClient-RequestId':str(self.RequestId),'X-Unity-Version':'2018.4.28f1'}
		return r

	def game_start(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/game/start',data={})
		return data

	def menu_locale_en(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/menu/locale/en',data={})
		return data

	def languages(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/languages',data={})
		return data

	def game_config(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/game/config',data={})
		return data

	def game_keepalive(self,sk=False):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/game/keepalive',data={})
		if not sk:	self.wait(40,40)
		return data

	def items(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/items',data={})
		return data

	def customization(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/customization',data={})
		return data

	def captcha_get(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/captcha/get',data={'locale':'en'})
		return data

	def captcha_validate(self,items,itype):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/captcha/validate',data={'items':items,'type':itype,'locale':'en'})
		return data

	def trysolvecaptcha(self):
		cap=self.captcha_get()
		lookingfor=cap['data']['description'].split('<b> ')[-1]
		lookingfor=str(lookingfor.rstrip())
		self.log('lookingfor:"%s"'%(lookingfor))
		lookingforid=self.getIdByWord(lookingfor)
		if not lookingforid:
			exit(1)
		self.log('lookingforid:%s'%(lookingforid))
		res=[]
		for i in cap['data']['items']:
			self.log('found:%s , is it right? %s'%(i,i==lookingforid))
			if i==lookingforid:
				res.append(i)
		if len(res)<=0:
			self.log('did not solve captcha!')
			return self.trysolvecaptcha()
		if not hasattr(self,'doingsnipe'):
			self.wait(1,3)
		else:
			self.wait(0,1)
		self.captcha_validate(res,cap['data']['type'])

	def globals(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/globals',data={})
		return data

	def game_profile_list(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/game/profile/list',data={})
		return data

	def game_profile_select(self,_id):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/game/profile/select',data={'uid': _id})
		return data

	def profile_status(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/profile/status',data={})
		return data

	def weather(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/weather',data={})
		return data

	def locale_en(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/locale/en',data={})
		return data

	def locations(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/locations',data={})
		return data

	def handbook_templates(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/handbook/templates',data={})
		return data

	def hideout_areas(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/hideout/areas',data={})
		return data

	def hideout_settings(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/hideout/settings',data={})
		return data

	def hideout_production_recipes(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/hideout/production/recipes',data={})
		return data

	def hideout_production_scavcase_recipes(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/hideout/production/scavcase/recipes',data={})
		return data

	def handbook_builds_my_list(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/handbook/builds/my/list',data={})
		return data

	def quest_list(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/quest/list',data={})
		return data

	def notifier_channel_create(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/notifier/channel/create',data={})
		return data

	def getprices(self,trader):
		data=self.callAPI('https://trading.escapefromtarkov.com/client/trading/api/getUserAssortPrice/trader/'+trader,data={})
		return data

	def ragfair_find(self,w,limit=100):
		data=self.callAPI('https://ragfair.escapefromtarkov.com/client/ragfair/find',data={"priceFrom":0,"conditionTo":100,"currency":1,"sortDirection":0,"onlyFunctional":True,"quantityFrom":0,"offerOwnerType":2,"tm":3,"linkedSearchId":"","conditionFrom":0,"priceTo":0,"sortType":5,"oneHourExpiration":False,"buildItems":{},"handbookId":w,"buildCount":0,"reload":17,"limit":limit,"quantityTo":0,"updateOfferCount":True,"neededSearchId":"","page":0,"removeBartering":True})
		return data

	def game_profile_items_moving_sell(self,items):
		res=[]
		for item in items:
			if 'upd' not in item or 'StackObjectsCount' not in item['upd']:
				res.append({"count":1,"id":item['_id'],"scheme_id":0})
			else:
				res.append({"count":item['upd']['StackObjectsCount'],"id":item['_id'],"scheme_id":0})
		if len(res)<=0:	return
		data={"reload":4,"tm":7,"data":[{"Action":"TradingConfirm","tid":self.NPC[self.getNPC(item['_tpl'])]['_id'],"type":"sell_to_trader","items":res}]}
		data=self.callAPI('https://prod.escapefromtarkov.com/client/game/profile/items/moving',data=data)
		return data

	def game_profile_items_moving(self,offer):
		#cachedprice=self.getprice(offer['items'][0]['_tpl'],bought=False)
		#self.log('Buy ' + offer['items'][0]['_tpl'] + ' ( ' + self.all_item_list[offer['items'][0]['_tpl']]['_props']['Name'] + ' )' + ' at ' + str(offer['requirementsCost']) + ' / ' + str(int(offer['itemsCost'] * self.multiplier)))
		offer_id = offer['_id']
		offer_count = offer['items'][0]['upd']['StackObjectsCount']
		offer_price = offer['items'][0]['upd']['StackObjectsCount'] * offer['summaryCost']
		start_time = offer['startTime']
		start_from = 56 #wait alteast for 56
		spent_time = time.time() - start_time
		if spent_time < start_from:
			to_wait = start_from - spent_time
			time.sleep(to_wait / 100) #division equals random wait timer
		data={"reload":4,"tm":7,"data":[{"Action":"RagFairBuyOffer","offers":[{"count":offer_count,"items":[],"id":offer_id}]}]}
		items = []
		for (id, value) in self.moneyStacks.items():
			if value >= offer_price:
				items.append((id, offer_price))
				break
			else:
				offer_price -= value
				items.append((id, value))
		for item in items:
			stack_info = dict()
			stack_info['id'] = item[0]
			stack_info['count'] = item[1]
			data['data'][0]['offers'][0]['items'].append(stack_info)
		data=self.callAPI('https://prod.escapefromtarkov.com/client/game/profile/items/moving',data=data)
		return data

	def mail_dialog_list(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/mail/dialog/list',data={})
		return data

	def game_version_validate(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/game/version/validate',data={"version":{"taxonomy":"341","major":self.clientversion,"game":"live","minor":"live","backend":"6"},"develop":True})
		return data

	def friend_list(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/friend/list',data={})
		return data

	def friend_request_list_inbox(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/friend/request/list/inbox',data={})
		return data

	def friend_request_list_outbox(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/friend/request/list/outbox',data={})
		return data

	def trading_customization_storage(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/trading/customization/storage',data={})
		return data

	def trading_api_getTradersList(self):
		data=self.callAPI('https://trading.escapefromtarkov.com/client/trading/api/getTradersList',data={})
		return data

	def server_list(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/server/list',data={})
		return data

	def checkVersion(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/checkVersion',data={})
		return data

	def game_logout(self):
		data=self.callAPI('https://prod.escapefromtarkov.com/client/game/logout',data={})
		return data

	def getpmc(self):
		profile=self.game_profile_list()
		for p in profile['data']:
			if p['Info']['Side'] != 'Savage':
				self.profile=p
				break

	def setprofile(self,skip=False):
		if not skip:
			self.game_start()
			#self.menu_locale_en()
			#self.game_version_validate()
			#self.languages()
			#self.game_config()
			#self.items()
			#self.customization()
			#self.globals()
		#if not hasattr(self,'moneyStacks'):
		self.moneyStacks={}
		self.getpmc()
		_inventory = dict()
		for item in self.profile['Inventory']['items']:
			_inventory[item['_id']] = item
		if hasattr(self,'balance'):
			self.oldbalance=self.balance
		else:
			self.oldbalance=None
		self.balance = 0
		for item_id, item in _inventory.items():
			if item['_tpl'] == const.rubles:
				count = item['upd']['StackObjectsCount']
				self.balance += count
				self.moneyStacks[item_id] = count
		if self.oldbalance is not None and (self.balance-self.oldbalance)>=10000:
			self.log('did we make profit? %s$ / %s$ [%s] bought %s\n'%(self.balance-self.oldbalance,self.balance,self.nickname,self.lastbought))
			self.lastbought=None
		else:
			self.log('have %s$'%(self.balance))
		self.game_profile_select(str(self.profile['_id'].rstrip()))
		self.profile_status()
		self.all_item_list=self.items()['data']
		self.findTraders()

	def findTraders(self):
		if not hasattr(self,'NPC'):
			self.NPC={}
			self.traders_list=self.trading_api_getTradersList()['data']
			for t in self.traders_list:
				self.log('found trader:%s [%s]'%(self.getEng(t['_id']),t['_id']))
				#if 'Therapis' in self.getEng(t['_id']):
				self.NPC[self.getEng(t['_id'])]={'_id':t['_id']}

	def getEng(self,i):
		if self.isLocal:
			if i in eng_local.data:
				return eng_local.data[i]
		else:
			if i in eng_live.data:
				return eng_live.data[i]
		return None

	def getIdByWord(self,i):
		for j in eng_live.data:
			if i in eng_live.data[j]:
				return j

	def exportText(self):
		data=self.locale_en()
		#data=jsb(data)
		j={}
		for i in data['data']['templates']:
			j[i]=data['data']['templates'][i]['Name']
		for i in data['data']['handbook']:
			j[i]=data['data']['handbook'][i]
		for i in data['data']['trading']:
			j[i]=data['data']['trading'][i]['Nickname']
		save('# -*- coding: utf-8 -*-\ndata=%s'%jsb(j),'eng_%s.py'%('live' if not self.isLocal else 'local'))

	def getNPC(self,item):
		return self.sessionnpc
		item=str(item)
		for v in vendors.data:
			if item in vendors.data[v]:
				self.log('found vendor:%s'%(v))
				return v
		self.log('didnt find vendor:%s'%(item))
		return None

	def cacheprices(self,item):
		self.slots={}
		res=self.getprices(self.NPC[self.getNPC(item)]['_id'])['data']
		self.getpmc()
		for j in self.profile['Inventory']['items']:
			self.slots[j['_id']]=j['_tpl']
		for i in res:
			if i not in self.slots:	continue
			StackObjectsCount=1
			for x in self.profile['Inventory']['items']:
				if x['_id'] != i:	continue
				if 'upd' not in x:	continue
				if 'StackObjectsCount' not in x['upd']:	continue
				StackObjectsCount=x['upd']['StackObjectsCount']
				break
			if StackObjectsCount>1:
				price=int(int(res[i][0][0]['count'])/StackObjectsCount)
			else:
				price=int(res[i][0][0]['count'])
			if self.db.needupdate(self.slots[i]):
				self.log('updating old price!')
				self.db.updatePrice(self.slots[i],price)

	def getprice(self,item,bought=True):
		if self.db.needupdate(item) and bought:
			self.log('forcing to update price')
			self.cacheprices(item)
		return self.db.getPrice(item)

	def wait(self,n,m):
		time.sleep(random.uniform(n+1,m+1))

	def getitemsforvendor(self,vendor):
		return list(set(vendors.data[vendor]))

	def gosnipe(self):
		self.doingsnipe=True
		wish=list(const.highitems)
		random.shuffle(wish)
		self.log('have %s in wish'%(len(wish)))
		for w in wish:
			self.log('looking for:%s [%s]'%(self.getEng(w),w))
			offers=self.ragfair_find(w)
			if offers is  None:
				offers=self.ragfair_find(w)
			offers=offers['data']['offers']
			if len(offers)<=5:
				self.log('no offers found!')
				continue
			prices=[int(x['summaryCost']) for x in offers]
			avgprices=sum(prices)/len(prices)
			self.log('found %s offers! avg price:%s$'%(len(offers),round(avgprices,2)))
			canBuy=False
			for j,o in enumerate(offers):
				summaryCost=int(o['summaryCost'])
				canBuy=summaryCost<=avgprices*0.70 and summaryCost<int(offers[j]['summaryCost'])
				if canBuy:
					result_data =self.game_profile_items_moving(o)
					if not result_data:
						self.log('did not buy it :(')
					else:
						self.log('profit we bought %s for %s$ while avg:%s$ next:%s$'%(self.getEng(w),int(o['summaryCost']),avgprices,offers[j]['summaryCost']))
						self.wait(0,1)
						self.setprofile(True)
					canBuy=False
			self.wait(1,3)

	def goshopping(self,npc,forceBuy=False):
		#wish=const.wish2|const.wish4|const.wish1
		#wish=list(wish)
		self.sessionnpc=npc
		wish=self.getitemsforvendor(npc)
		random.shuffle(wish)
		self.log('have %s in wish'%(len(wish)))
		for w in wish:
			if npc == 'Mechanic' and self.getprice(w,False)<=1500:	continue
			self.log('looking for:%s [%s]'%(self.getEng(w),w))
			offers=self.ragfair_find(w)
			if offers is  None:
				offers=self.ragfair_find(w)
			offers=offers['data']['offers']
			if len(offers)<=0:
				self.log('no offers found!')
				#self.wait(3,5)
				continue
			bought=[]
			didPricecheck=False
			prices=[int(x['summaryCost']) for x in offers]
			self.log('found %s offers! avg price:%s$'%(len(offers),round(sum(prices)/len(prices),2)))
			for o in offers:
				cachedprice=self.getprice(o['items'][0]['_tpl'],bought=False)
				if cachedprice and cachedprice>(int(o['summaryCost'])+1):
					self.log('vendor has higher price! %s$ - %s$ = %s$'%(cachedprice,int(o['summaryCost']),cachedprice-int(o['summaryCost'])))
					forceBuy=True
				elif cachedprice and cachedprice<=int(o['summaryCost']):
					#self.log('price higher than vendor, skipping! cachedprice:%s$ summaryCost:%s$'%(cachedprice,o['summaryCost']))
					continue
				else:
					pass
					#self.log('itemsCost:%s * %s:%s summaryCost:%s min_price:%s = %s'%(o['itemsCost'],self.multiplier,int(o['itemsCost'] * self.multiplier),o['summaryCost'],self.min_price,int(o['itemsCost'] * self.multiplier) - o['summaryCost']))
				if int(o['itemsCost'] * self.multiplier) - o['summaryCost'] > self.min_price or forceBuy:
					if int(o['items'][0]['upd']['StackObjectsCount'])<=0:	continue
					self.log('could buy %s [%s] for %s$ * %s'%(self.getEng(o['items'][0]['_tpl']),o['items'][0]['_tpl'],int(o['summaryCost']),int(o['items'][0]['upd']['StackObjectsCount'])))
					result_data =self.game_profile_items_moving(o)
					forceBuy=False
					if not result_data:
						self.log('we didnt buy item!')
						self.wait(0,1)
						continue
					if len(result_data['data']['items'].keys()) > 0:
						for item in result_data['data']['items']['new']:
							bought.append(item)
					if len(bought)>=1 and not didPricecheck:
						if not self.getprice(o['items'][0]['_tpl'],bought=True):
							self.log('vendor does not buy item')
							break
						didPricecheck=True
						self.wait(0,1)
					self.wait(1,2)
			if len(bought)>=1:
				if not self.game_profile_items_moving_sell(bought):
					self.game_profile_items_moving_sell(bought)
				self.wait(2,5)
				self.lastbought=self.getEng(o['items'][0]['_tpl'])
				self.setprofile(True)
				self.wait(5,7)
			else:
				self.wait(0,1)
			#exit(1)

	def spawncheck(self):
		if hasattr(self,'didSpawn'):	return
		t = threading.Thread(target=self.game_keepalive)
		t.daemon = True
		t.start()
		self.didSpawn=True

class const(object):
	rubles='5449016a4bdc2d6f028b456f'
	wish1=set(['5ad7247386f7747487619dc3','5a0ee34586f774023b6ee092','5c127c4486f7745625356c13','5c1e2a1e86f77431ea0ea84c','5a13ef0686f7746e5a411744','5a0f08bc86f77478f33b84c2','5a1452ee86f7746f33111763','5a0eecf686f7740350630097','5a0ee76686f7743698200d5c','5913915886f774123603c392','5a0ee4b586f7743698200d22','5a144bdb86f7741d374bbde0','5a0ee37f86f774023657a86f','5a0eeb1a86f774688b70aa5c','5c052f6886f7746b1e3db148','5a0eedb386f77403506300be','5addaffe86f77470b455f900','5c052e6986f7746b207bc3c9','5da5cdcd86f774529238fb9b','5b43575a86f77424f443fe62','5ad7217186f7746744498875','5ad7242b86f7740a6a3abd43','5a13ee1986f774794d4c14cd','5a0ee72c86f77436955d3435','5d1b327086f7742525194449','5c1e2d1f86f77431e9280bee','5c1f79a086f7746ed066fb8f','5ad5d64486f774079b080af8','5d1b2f3f86f774252167a52c','5a0eebed86f77461230ddb3d','5d0377ce86f774186372f689','5780cf942459777df90dcb72','5bc9bc53d4351e00367fbcee','5d80c93086f7744036212b41','5a0ee62286f774369454a7ac','5a0f006986f7741ffd2fe484','5d1b32c186f774252167a530','5bc9b9ecd4351e3bac122519','5a0ec70e86f7742c0b518fba','5bc9c049d4351e44f824d360','5a0ea69f86f7741cd5406619','5a0eeb8e86f77461257ed71a','590de7e986f7741b096e5f32','5d0378d486f77420421a5ff4','59e3647686f774176a362507','5d03784a86f774203e7e0c4d','5bc9bdb8d4351e003562b8a1','5bc9b720d4351e450201234b','5bc9c377d4351e3bac12251b','5a0f045e86f7745b0f0d0e42','59e3658a86f7741776641ac4','5d403f9186f7743cac3f229b','590de71386f774347051a052','5ad5d20586f77449be26d877','5d0375ff86f774186372f685','5d1b304286f774253763a528','5734758f24597738025ee253','5d235b4d86f7742e017bc88a','59136e1e86f774432f15d133','5d80cb8786f774405611c7d9','5c0e534186f7747fa1419867','5a0f075686f7745bcc42ee12','5c1265fc86f7743f896a21c2','5ad5ccd186f774446d5706e9','5c0e531286f7747fa54205c2','5bc9be8fd4351e00334cae6e','5d1b385e86f774252167b98a','5af0561e86f7745f5f3ad6ac','5c0e533786f7747fa23f4d47','5d40407c86f774318526545a','5734773724597737fd047c14','5c10c8fd86f7743d7d706df3','590a3b0486f7743954552bdb','5d1b39a386f774252339976f','5c0e530286f7747fa1419862','5af04b6486f774195a3ebb49','5a8036fb86f77407252ddc02','573477e124597737dd42e191','590a3efd86f77437d351a25b','590c5c9f86f77477c91c36e7','590a391c86f774385a33c404','59faf98186f774067b6be103','5780d0532459777a5108b9a2','590a3c0a86f774385a33c450','590a358486f77429692b2790','56742c324bdc2d150f8b456d','591383f186f7744a4c5edcf3','590c35a486f774273531c822','5913877a86f774432f15d444','593aa4be86f77457f56379f8','5a0eb38b86f774153b320eb0','5751496424597720a27126da','544fb3f34bdc2d03748b456a','574eb85c245977648157eec3','57347baf24597738002c6178','59e3556c86f7741776641ac2','5d1b3f2d86f774253763b735','590c5bbd86f774785762df04','59136a4486f774447a1ed172','590c2d8786f774245b1f03f3','5939a00786f7742fe8132936','57347c77245977448d35f6e2','5798a2832459774b53341029','5751435d24597720a27126d1','5d40412b86f7743cb332ac3a','5c13cef886f774072e618e82','590c5a7286f7747884343aea','59e361e886f774176c10a2a5','5900b89686f7744e704a8747','5c13cd2486f774072c757944','5bc9c29cd4351e003562b8a3','5d40425986f7743185265461','57505f6224597709a92585a9','5d4042a986f7743185265463','5937ee6486f77408994ba448','57347d7224597744596b4e72','5d1b3a5d86f774252167ba22','593962ca86f774068014d9af','590c695186f7741e566b64a2','5938504186f7740991483f30','5672cb304bdc2dc2088b456a','5d1c819a86f774771b0acd6c','59e358a886f7741776641ac3','59e366c186f7741778269d85','5780cf692459777de4559321','59148f8286f7741b951ea113','57347cd0245977445a2d6ff1','57347d692459774491567cf1','57347d3d245977448f7b7f61','5d4041f086f7743cac3f22a7','5780d0652459777df90dcb74','59e3596386f774176c10a2a2','5780d0652459777df90dcb74','57347d3d245977448f7b7f61','59e3596386f774176c10a2a2','57347d692459774491567cf1','5d1b309586f77425227d1676','590a3d9c86f774385926e510','5734781f24597737e04bf32a','590c595c86f7747884343ad7','59148c8a86f774197930e983','5673de654bdc2d180f8b456d','5be4038986f774527d3fae60','590c2b4386f77425357b6123','5913611c86f77479e0084092','5938603e86f77435642354f4','544fb62a4bdc2dfb738b4568','5a80a29286f7742b25692012','575062b524597720a31c09a1','57347d5f245977448b40fa81','5913651986f774432f15d132','5448ff904bdc2d6f028b456e','590a3cd386f77436f20848cb','5780cf9e2459777df90dcb73','5780d07a2459777de4559324','544fb6cc4bdc2d34748b456e','573476f124597737e04bf328','5c06782b86f77426df5407d2','590c2c9c86f774245b1f03f2','5780cda02459777b272ede61','573474f924597738002c6174','5b7c710788a4506dec015957','5734779624597737e04bf329','5914578086f774123569ffa4','57a349b2245977762b199ec7','573476d324597737da2adc13','591382d986f774465a6413a7','5672c92d4bdc2d180f8b4567','57347c1124597737fb1379e3','5783c43d2459774bbe137486','57a349b2245977762b199ec7','5d1b31ce86f7742523398394','5672cb124bdc2d1a0f8b4568','5938994586f774523a425196','5780cf722459777a5108b9a1','57347c93245977448d35f6e3','544fb3364bdc2d34748b456a','573475fb24597737fb1379e1','5909e99886f7740c983b9984','5734770f24597738025ee254','544fb25a4bdc2dfb738b4567','59136f6f86f774447a1ed173','56742c284bdc2d98058b456d','57347b8b24597737dd42e192','591ae8f986f77406f854be45'])
	wish2=set(['5c1d0efb86f7744baf2e7b7b','5c0a840b86f7742ffa4f2482','59fb042886f7746c5005a7b2','5b6d9ce188a4501afc1b2b25','5c1d0c5f86f7744bb2683cf0','5c1d0dc586f7744baf2e7b79','5d235bb686f77443f4331278','5c1e495a86f7743109743dfb','59fb023c86f7746d0d4b423c','5c0530ee86f774697952d952','59fafd4b86f7745ca07e1232','5d03794386f77420415576f5','5ad5d7d286f77450166e0a89','5d95d6fa86f77424484aa5e9','5d80cb5686f77440545d1286','5c093db286f7740a1b2617e3','5c1d0f4986f7744bb01837fa','5a0ee30786f774023b6ee08f','5d8e3ecc86f774414c78d05e','5d80cab086f77440535be201','590c60fc86f77412b13fddcf','5a0dc95c86f77452440fc675','5aafbcd986f7745e590fff23','5a13ef7e86f7741290491063','5c093e3486f77430cb02e593','5ad7247386f7747487619dc3','5da743f586f7744014504f72','5a13f46386f7741dd7384b04','5d80cbd886f77470855c26c2','5d1b376e86f774252519444e','5a0ee34586f774023b6ee092','59fb016586f7746d0d4b423a','5d947d4e86f774447b415895','5d80c8f586f77440373c4ed0','5ad5cfbd86f7742c825d6104','5d03775b86f774203e7e0c4b','5c127c4486f7745625356c13','59e3639286f7741777737013','5c1e2a1e86f77431ea0ea84c','5a13ef0686f7746e5a411744','5d8e0db586f7744450412a42','57347ca924597744596b4e71','5aafbde786f774389d0cbc0f','5a1452ee86f7746f33111763','5a0f08bc86f77478f33b84c2','5ad5db3786f7743568421cce','5733279d245977289b77ec24','5a0eecf686f7740350630097','5a0ee76686f7743698200d5c','5a13f35286f77413ef1436b0','5d9f1fa686f774726974a992','5d80ccdd86f77474f7575e02','5a13f24186f77410e57c5626','5913915886f774123603c392','5a0ee4b586f7743698200d22','5d80c78786f774403a401e3e','5d8e0e0e86f774321140eb56','5da46e3886f774653b7a83fe','5d1b33a686f7742523398398','59e3606886f77417674759a5','5d80c6c586f77440351beef1','5c12620d86f7743f8b198b72','5a13eebd86f7746fd639aa93','5a144bdb86f7741d374bbde0','5c1267ee86f77416ec610f72','5c94bbff86f7747ee735c08f','5a0ee37f86f774023657a86f','5a0eeb1a86f774688b70aa5c','5a0f0f5886f7741c4e32a472','5c052f6886f7746b1e3db148','5addaffe86f77470b455f900','5a0dc45586f7742f6b0b73e3','59faf7ca86f7740dbe19f6c2','5a0eee1486f77402aa773226','5a0eedb386f77403506300be','5d80c88d86f77440556dbf07','5c052e6986f7746b207bc3c9','5d947d3886f774447b415893','59e35cbb86f7741778269d83','5d80c66d86f774405611c7d6','590c2e1186f77425357b6124','5c05308086f7746b2101e90b','5a0ea64786f7741707720468','5d80cb3886f77440556dbf09','5d8e15b686f774445103b190','5af0534a86f7743b6f354284','5da5cdcd86f774529238fb9b','5b43575a86f77424f443fe62','5ad7242b86f7740a6a3abd43','5ad7217186f7746744498875','5a0ee72c86f77436955d3435','5d80ca9086f774403a401e40','5a13ee1986f774794d4c14cd','5d95d6be86f77424444eb3a7','5a0eb6ac86f7743124037a28','5d80c95986f77440351beef3','5c1f79a086f7746ed066fb8f','567143bf4bdc2d1a0f8b4567','5d0377ce86f774186372f689','5c1e2d1f86f77431e9280bee','5d1b327086f7742525194449','5d0376a486f7747d8050965c','5a145d4786f7744cbb6f4a12','5780cfa52459777dfb276eb1','5bc9bc53d4351e00367fbcee','5d80cd1a86f77402aa362f42','5d6fc78386f77449d825f9dc','5751a89d24597722aa0e8db0','5a0eebed86f77461230ddb3d','5d1b2f3f86f774252167a52c','5ad5d64486f774079b080af8','5c05300686f7746dce784e5d','5a0ee62286f774369454a7ac','5d80c93086f7744036212b41','5d1b32c186f774252167a530','5bc9b9ecd4351e3bac122519','5a0f006986f7741ffd2fe484','5ad5d20586f77449be26d877','5a0eec9686f77402ac5c39f2','5bc9c049d4351e44f824d360','5d235a5986f77443f6329bc6','59fafb5d86f774067a6f2084','5d80c6fc86f774403a401e3c','5a0ea69f86f7741cd5406619','5a0eeb8e86f77461257ed71a','5c12688486f77426843c7d32','590de7e986f7741b096e5f32','5780cf942459777df90dcb72','5d1b313086f77425227d1678','5a145d7b86f7744cbb6f4a13','5a0ea79b86f7741d4a35298e','5d1b2fa286f77425227d1674','59e3647686f774176a362507','5a0eed4386f77405112912aa','5d0378d486f77420421a5ff4','5d03784a86f774203e7e0c4d','5c0e531d86f7747fa23f4d42','5a0ec70e86f7742c0b518fba','5bc9bdb8d4351e003562b8a1','5d80ccac86f77470841ff452','5d0379a886f77420407aa271','5bc9b720d4351e450201234b','5bc9c377d4351e3bac12251b','59e3658a86f7741776641ac4','5a0f068686f7745b0d4ea242','5b4335ba86f7744d2837a264','57347c2e24597744902c94a1','5d1b2ffd86f77425243e8d17','5d40419286f774318526545f','59e35de086f7741778269d84','5d403f9186f7743cac3f229b','5c052fb986f7746b2101e909','590de71386f774347051a052','590a373286f774287540368b','5a0ec6d286f7742c0b518fb5','5d235b4d86f7742e017bc88a','5a0f045e86f7745b0f0d0e42','590c346786f77423e50ed342','5734758f24597738025ee253','59e36c6f86f774176c10a2a7','5d0375ff86f774186372f685','5938144586f77473c2087145','5d1b304286f774253763a528','5734795124597738002c6176','5d1b392c86f77425243e98fe','5af04b6486f774195a3ebb49','5d80cb8786f774405611c7d9','591afe0186f77431bd616a11','5bc9be8fd4351e00334cae6e','59136e1e86f774432f15d133','59faf98186f774067b6be103','5a144dfd86f77445cb5a0982','5ad5ccd186f774446d5706e9','590c5f0d86f77413997acfab','5c0e534186f7747fa1419867','5c1265fc86f7743f896a21c2','59e35ef086f7741777737012','5d1c774f86f7746d6620f8db','59e35abd86f7741778269d82','590c311186f77424d1667482','5c0e531286f7747fa54205c2','5a0f075686f7745bcc42ee12','5af0454c86f7746bf20992e8','57347c5b245977448d35f6e1','57347d8724597744596b4e76','5af0561e86f7745f5f3ad6ac','5c0e533786f7747fa23f4d47','5be4038986f774527d3fae60','5d1b39a386f774252339976f','57347d9c245977448b40fa85','59387a4986f77401cc236e62','5734773724597737fd047c14','5a145ebb86f77458f1796f05','590c5d4b86f774784e1b9c45','593aa4be86f77457f56379f8','5751487e245977207e26a315','5c10c8fd86f7743d7d706df3','5d1b385e86f774252167b98a','575146b724597720a27126d5','5d6fc87386f77449db3db94e','5d63d33b86f7746ea9275524','5c0e530286f7747fa1419862','57347da92459774491567cf5','5a0eff2986f7741fd654e684','590c35a486f774273531c822','590c5c9f86f77477c91c36e7','57514643245977207f2c2d09','59e3556c86f7741776641ac2','5c06779c86f77426e00dd782','59e358a886f7741776641ac3','5939a00786f7742fe8132936','5af0484c86f7740f02001f7f','5751435d24597720a27126d1','590a3b0486f7743954552bdb','590a391c86f774385a33c404','5780d0532459777a5108b9a2','590a3efd86f77437d351a25b','590a358486f77429692b2790','56742c324bdc2d150f8b456d','57347d3d245977448f7b7f61','590a386e86f77429692b27ab','573477e124597737dd42e191','5913877a86f774432f15d444','5672cb724bdc2dc2088b456b','544fb3f34bdc2d03748b456a','591383f186f7744a4c5edcf3','574eb85c245977648157eec3','57347baf24597738002c6178','57347d692459774491567cf1','59e3556c86f7741776641ac2','5d1c819a86f774771b0acd6c','5937ee6486f77408994ba448','59136a4486f774447a1ed172','544fb62a4bdc2dfb738b4568','5d1b3f2d86f774253763b735','5ad5d49886f77455f9731921','590c5bbd86f774785762df04','5d1b309586f77425227d1676','5bc9c29cd4351e003562b8a3','57347c77245977448d35f6e2','5a8036fb86f77407252ddc02','5a8036fb86f77407252ddc02','5d1b3a5d86f774252167ba22','59148c8a86f774197930e983','5d4042a986f7743185265463','5c06782b86f77426df5407d2','5c13cd2486f774072c757944','5a0eb38b86f774153b320eb0','5d40412b86f7743cb332ac3a','590a3d9c86f774385926e510','5a80a29286f7742b25692012','5900b89686f7744e704a8747','57347d7224597744596b4e72','5d40425986f7743185265461','59e3596386f774176c10a2a2','5751496424597720a27126da','590c5a7286f7747884343aea','5780cf692459777de4559321','59148f8286f7741b951ea113','5673de654bdc2d180f8b456d','5938504186f7740991483f30','577e1c9d2459773cd707c525','590c2d8786f774245b1f03f3','59e366c186f7741778269d85','5780d0652459777df90dcb74','5672cb304bdc2dc2088b456a','590a3c0a86f774385a33c450','59e361e886f774176c10a2a5','5798a2832459774b53341029','5448ff904bdc2d6f028b456e','590c595c86f7747884343ad7','590a3cd386f77436f20848cb','590c695186f7741e566b64a2','57505f6224597709a92585a9','5c13cef886f774072e618e82','5938603e86f77435642354f4','5913611c86f77479e0084092','5913651986f774432f15d132','5783c43d2459774bbe137486','593962ca86f774068014d9af','57347c1124597737fb1379e3','5734781f24597737e04bf32a','590c2b4386f77425357b6123','5909e99886f7740c983b9984','575062b524597720a31c09a1','5780cf9e2459777df90dcb73','573476f124597737e04bf328','5b7c710788a4506dec015957','5672cb124bdc2d1a0f8b4568','590c2c9c86f774245b1f03f2','544fb6cc4bdc2d34748b456e','5780d07a2459777de4559324','5b7c710788a4506dec015957','57a349b2245977762b199ec7','5d4041f086f7743cac3f22a7','57347d5f245977448b40fa81','573474f924597738002c6174','5914578086f774123569ffa4','5734779624597737e04bf329','5780cda02459777b272ede61','5672c92d4bdc2d180f8b4567','591382d986f774465a6413a7','57a349b2245977762b199ec7','573475fb24597737fb1379e1','57347cd0245977445a2d6ff1','57347c93245977448d35f6e3','544fb3364bdc2d34748b456a','5d1b31ce86f7742523398394','5938994586f774523a425196','5734770f24597738025ee254','544fb25a4bdc2dfb738b4567','5780cf722459777a5108b9a1','57347b8b24597737dd42e192','573476d324597737da2adc13','59136f6f86f774447a1ed173','591ae8f986f77406f854be45','56742c284bdc2d98058b456d'])
	wish3=set(['544fb25a4bdc2dfb738b4567'])
	wish4=set(['5448ba0b4bdc2d02308b456c','5448fee04bdc2dbc018b4567','5448ff904bdc2d6f028b456e','544fb25a4bdc2dfb738b4567','544fb3364bdc2d34748b456a','544fb37f4bdc2dee738b4567','544fb3f34bdc2d03748b456a','544fb45d4bdc2dee738b4568','544fb62a4bdc2dfb738b4568','544fb6cc4bdc2d34748b456e','567143bf4bdc2d1a0f8b4567','5672c92d4bdc2d180f8b4567','5673de654bdc2d180f8b456d','573474f924597738002c6174','5734758f24597738025ee253','573475fb24597737fb1379e1','573476d324597737da2adc13','573476f124597737e04bf328','5734770f24597738025ee254','5734773724597737fd047c14','573478bc24597738002c6175','57347d3d245977448f7b7f61','57347d5f245977448b40fa81','57347d692459774491567cf1','57347d7224597744596b4e72','57347d8724597744596b4e76','57347d90245977448f7b7f65','57347d9c245977448b40fa85','57347da92459774491567cf5','574eb85c245977648157eec3','57505f6224597709a92585a9','575062b524597720a31c09a1','57513f07245977207e26a311','57513f9324597720a7128161','57513fcc24597720a31c09a6','5751435d24597720a27126d1','57514643245977207f2c2d09','575146b724597720a27126d5','5751487e245977207e26a315','5751496424597720a27126da','5751a25924597722c463c472','5751a89d24597722aa0e8db0','5755356824597772cb798962','5755383e24597772cb798966','5780cda02459777b272ede61','5780cf692459777de4559321','5780cf722459777a5108b9a1','5780cf7f2459777de4559322','5780cf942459777df90dcb72','5780cf9e2459777df90dcb73','5780cfa52459777dfb276eb1','5780d0532459777a5108b9a2','5780d0652459777df90dcb74','5780d07a2459777de4559324','5783c43d2459774bbe137486','5798a2832459774b53341029','57a349b2245977762b199ec7','5900b89686f7744e704a8747','590c37d286f77443be3d7827','590c392f86f77444754deb29','590c595c86f7747884343ad7','590c5d4b86f774784e1b9c45','590c5f0d86f77413997acfab','590c60fc86f77412b13fddcf','590c621186f774138d11ea29','590c639286f774151567fa95','590c645c86f77412b01304d9','590c651286f7741e566b6461','590c657e86f77412b013051d','590c661e86f7741e566b646a','590c678286f77426c9660122','590c695186f7741e566b64a2','590de71386f774347051a052','590de7e986f7741b096e5f32','5913611c86f77479e0084092','5913651986f774432f15d132','59136a4486f774447a1ed172','59136e1e86f774432f15d133','59136f6f86f774447a1ed173','591382d986f774465a6413a7','591383f186f7744a4c5edcf3','5913877a86f774432f15d444','5913915886f774123603c392','5914578086f774123569ffa4','59148c8a86f774197930e983','59148f8286f7741b951ea113','591ae8f986f77406f854be45','591afe0186f77431bd616a11','5937ee6486f77408994ba448','5938144586f77473c2087145','5938504186f7740991483f30','593858c486f774253a24cb52','5938603e86f77435642354f4','59387a4986f77401cc236e62','5938994586f774523a425196','593962ca86f774068014d9af','593aa4be86f77457f56379f8','59e3577886f774176a362503','59e3606886f77417674759a5','59e361e886f774176c10a2a5','59e3639286f7741777737013','59e3647686f774176a362507','59e3658a86f7741776641ac4','59f32bb586f774757e1e8442','59f32c3b86f77472a31742f0','59faf7ca86f7740dbe19f6c2','59fafd4b86f7745ca07e1232','59faff1d86f7746c51718c9c','59fb016586f7746d0d4b423a','59fb023c86f7746d0d4b423c','59fb042886f7746c5005a7b2','5a0dc45586f7742f6b0b73e3','5a0dc95c86f77452440fc675','5a0ea64786f7741707720468','5a0ea69f86f7741cd5406619','5a0ea79b86f7741d4a35298e','5a0eb38b86f774153b320eb0','5a0eb6ac86f7743124037a28','5a0ec6d286f7742c0b518fb5','5a0ec70e86f7742c0b518fba','5a0ee30786f774023b6ee08f','5a0ee34586f774023b6ee092','5a0ee37f86f774023657a86f','5a0ee4b586f7743698200d22','5a0ee62286f774369454a7ac','5a0ee72c86f77436955d3435','5a0ee76686f7743698200d5c','5a0eeb1a86f774688b70aa5c','5a0eeb8e86f77461257ed71a','5a0eebed86f77461230ddb3d','5a0eec9686f77402ac5c39f2','5a0eecf686f7740350630097','5a0eed4386f77405112912aa','5a0eedb386f77403506300be','5a0eee1486f77402aa773226','5a0eff2986f7741fd654e684','5a0f006986f7741ffd2fe484','5a0f045e86f7745b0f0d0e42','5a0f068686f7745b0d4ea242','5a0f075686f7745bcc42ee12','5a0f08bc86f77478f33b84c2','5a0f0f5886f7741c4e32a472','5a13ee1986f774794d4c14cd','5a13eebd86f7746fd639aa93','5a13ef0686f7746e5a411744','5a13ef7e86f7741290491063','5a13f24186f77410e57c5626','5a13f35286f77413ef1436b0','5a13f46386f7741dd7384b04','5a144bdb86f7741d374bbde0','5a144dfd86f77445cb5a0982','5a1452ee86f7746f33111763','5a145d4786f7744cbb6f4a12','5a145d7b86f7744cbb6f4a13','5a145ebb86f77458f1796f05','5a8036fb86f77407252ddc02','5a80a29286f7742b25692012','5aafbcd986f7745e590fff23','5aafbde786f774389d0cbc0f','5ad5ccd186f774446d5706e9','5ad5cfbd86f7742c825d6104','5ad5d20586f77449be26d877','5ad5d49886f77455f9731921','5ad5d64486f774079b080af8','5ad5d7d286f77450166e0a89','5ad5db3786f7743568421cce','5ad7217186f7746744498875','5ad7242b86f7740a6a3abd43','5ad7247386f7747487619dc3','5addaffe86f77470b455f900','5af0454c86f7746bf20992e8','5af0484c86f7740f02001f7f','5af0534a86f7743b6f354284','5af0548586f7743a532b7e99','5b4335ba86f7744d2837a264','5b47574386f77428ca22b2f1','5b47574386f77428ca22b2f3','5b47574386f77428ca22b2f4','5b5f6fa186f77409407a7eb7','5b6d9ce188a4501afc1b2b25','5b7c710788a4506dec015957','5bc9b156d4351e00367fbce9','5bc9bc53d4351e00367fbcee','5bc9bdb8d4351e003562b8a1','5bc9be8fd4351e00334cae6e','5bc9c049d4351e44f824d360','5bc9c29cd4351e003562b8a3','5bc9c377d4351e3bac12251b','5be4038986f774527d3fae60','5c052e6986f7746b207bc3c9','5c0530ee86f774697952d952','5c093db286f7740a1b2617e3','5c093e3486f77430cb02e593','5c0a840b86f7742ffa4f2482','5c0e530286f7747fa1419862','5c0e531286f7747fa54205c2','5c0e531d86f7747fa23f4d42','5c0e533786f7747fa23f4d47','5c0e534186f7747fa1419867','5c0fa877d174af02a012e1cf','5c10c8fd86f7743d7d706df3','5c12613b86f7743bbe2c3f76','5c1267ee86f77416ec610f72','5c12688486f77426843c7d32','5c127c4486f7745625356c13','5c1d0c5f86f7744bb2683cf0','5c1d0d6d86f7744bb2683e1f','5c1d0dc586f7744baf2e7b79','5c1d0efb86f7744baf2e7b7b','5c1d0f4986f7744bb01837fa','5c1e2a1e86f77431ea0ea84c','5c1e2d1f86f77431e9280bee','5c1e495a86f7743109743dfb','5c1f79a086f7746ed066fb8f','5c94bbff86f7747ee735c08f','5d02778e86f774203e7dedbe','5d02797c86f774203f38e30a','5d0379a886f77420407aa271','5d08d21286f774736e7c94c3','5d1b2f3f86f774252167a52c','5d1b33a686f7742523398398','5d1b376e86f774252519444e','5d1b385e86f774252167b98a','5d1b3a5d86f774252167ba22','5d1b3f2d86f774253763b735','5d1c819a86f774771b0acd6c','5d235a5986f77443f6329bc6','5d235b4d86f7742e017bc88a','5d235bb686f77443f4331278','5d403f9186f7743cac3f229b','5d40407c86f774318526545a','5d80c60f86f77440373c4ece','5d80c62a86f7744036212b3f','5d80c66d86f774405611c7d6','5d80c6c586f77440351beef1','5d80c6fc86f774403a401e3c','5d80c78786f774403a401e3e','5d80c88d86f77440556dbf07','5d80c8f586f77440373c4ed0','5d80c93086f7744036212b41','5d80c95986f77440351beef3','5d80ca9086f774403a401e40','5d80cab086f77440535be201','5d80cb3886f77440556dbf09','5d80cb5686f77440545d1286','5d80cb8786f774405611c7d9','5d80cbd886f77470855c26c2','5d80ccac86f77470841ff452','5d80ccdd86f77474f7575e02','5d80cd1a86f77402aa362f42','5d8e0db586f7744450412a42','5d8e0e0e86f774321140eb56','5d8e15b686f774445103b190','5d8e3ecc86f774414c78d05e','5d947d3886f774447b415893','5d947d4e86f774447b415895','5d95d6be86f77424444eb3a7','5d95d6fa86f77424484aa5e9','5d9f1fa686f774726974a992','5da46e3886f774653b7a83fe','5da5cdcd86f774529238fb9b','5da743f586f7744014504f72','5df8a6a186f77412640e2e80','5df8a72c86f77412640e2e83','5df8a77486f77412672a1e3f','5e2af41e86f774755a234b67','5e2af47786f7746d404f3aaa','5e2af4a786f7746d3f3c3400','5e2af4d286f7746d4159f07a','5e2af51086f7746d3f3c3402','5e2af55f86f7746d4159f07c','5e42c71586f7747f245e1343','5e42c81886f7742a01529f57','5e42c83786f7742a021fdf3c','5e54f62086f774219b0f1937','5e54f6af86f7742199090bf3','5e831507ea0a7c419c2f9bd9','5e8488fa988a8701445df1e4','5e8f3423fd7471236e6e3b64','5ed515c8d380ab312177c0fa','5ed515e03a40a50460332579','5ed515ece452db0eb56fc028','5ed515f6915ec335206e4152','5ed5160a87bb8443d10680b5','5ed51652f6c34d2cc26336a1','5ed5166ad380ab312177c100','5ede7a8229445733cb4c18e2','5ede7b0c6d23e5473e6e8c66','5efde6b4f5448336730dbd61','5eff09cd30a7dc22fd1ddfed','5f745ee30acaeb0d490d8c5b','5fca138c2a7b221b2852a5c6','5fca13ca637ee0341a484f46'])
	highitems=set(['5e2af55f86f7746d4159f07c', '5c793fb92e221644f31bfb64', '5c093ca986f7740a1867ab12', '5a16b7e1fcdbcb00165aa6c9', '5df8a4d786f77412672a1e3b', '5780cf7f2459777de4559322', '5ea18c84ecf1982c7712d9a2', '5c0a840b86f7742ffa4f2482', '5a0ee30786f774023b6ee08f', '5e42c81886f7742a01529f57', '5c1d0efb86f7744baf2e7b7b', '5c0126f40db834002a125382', '5c0000c00db834001a6697fc', '5b44cd8b86f774503d30cba2', '5c0530ee86f774697952d952', '5d0379a886f77420407aa271', '5fd4c474dd870108a754b241', '60391afc25aff57af81f7085', '5d1b385e86f774252167b98a', '5ca21c6986f77479963115a7', '5e81ebcd8e146c7080625e15', '5e4abb5086f77406975c9342', '5d80c88d86f77440556dbf07', '5c1d0f4986f7744bb01837fa', '5aafbde786f774389d0cbc0f', '59faf7ca86f7740dbe19f6c2', '545cdb794bdc2d3a198b456a', '5f60c74e3b85f6263c145586', '5c05308086f7746b2101e90b', '5857a8b324597729ab0a0e7d', '5d03775b86f774203e7e0c4b', '5c1e495a86f7743109743dfb', '59fafd4b86f7745ca07e1232', '601948682627df266209af05', '5d80c66d86f774405611c7d6', '5b44cf1486f77431723e3d05', '5d9f1fa686f774726974a992', '59c63b4486f7747afb151c1c', '5c093e3486f77430cb02e593', '5efde6b4f5448336730dbd61', '57347ca924597744596b4e71', '59e3639286f7741777737013', '5c110624d174af029e69734c', '5a1eaa87fcdbcb001865f75e', '5ad5d7d286f77450166e0a89', '5d235bb686f77443f4331278', '5e4ac41886f77406a511c9a8', '5d947d3886f774447b415893', '5a0eb6ac86f7743124037a28', '5bffdd7e0db834001b734a1a', '5b44cad286f77402a54ae7e5', '5b6d9ce188a4501afc1b2b25', '5c0e541586f7747fa54205c9', '5b7c710788a4506dec015957', '5d1b376e86f774252519444e', '5d1b371186f774253763a656', '59db794186f77448bc595262', '5d03794386f77420415576f5', '5aafbcd986f7745e590fff23', '5c093db286f7740a1b2617e3', '5c94bbff86f7747ee735c08f', '6038b4ca92ec1c3103795a0d', '5ca2151486f774244a3b8d30', '59faff1d86f7746c51718c9c', '5e9dacf986f774054d6b89f4', '5c052e6986f7746b207bc3c9', '5c052fb986f7746b2101e909', '5e00c1ad86f774747333222c', '5c0558060db834001b735271', '5857a8bc2459772bad15db29', '5d1b2f3f86f774252167a52c', '5c127c4486f7745625356c13', '5c793fc42e221600114ca25d', '5c12613b86f7743bbe2c3f76', '5c0e625a86f7742d77340f62', '5751a89d24597722aa0e8db0', '5af0561e86f7745f5f3ad6ac', '59fb023c86f7746d0d4b423c', '5d1b5e94d7ad1a2b865a96b0', '59fb016586f7746d0d4b423a', '5ede7a8229445733cb4c18e2', '5c1d0dc586f7744baf2e7b79', '6038b4b292ec1c3103795a0b', '5e42c71586f7747f245e1343', '5e71f70186f77429ee09f183', '5d80ca9086f774403a401e40', '544a11ac4bdc2d470e8b456a', '5d1b36a186f7742523398433', '5d95d6be86f77424444eb3a7', '5b44d0de86f774503d30cba8', '5d80cb3886f77440556dbf09', '5bffe7930db834001b734a39', '5d8e0e0e86f774321140eb56', '5e42c83786f7742a021fdf3c', '590c60fc86f77412b13fddcf', '5f5f41476bdad616ad46d631', '5c1d0c5f86f7744bb2683cf0', '59fb042886f7746c5005a7b2', '5d08d21286f774736e7c94c3'])
	highitems=set(['5d03775b86f774203e7e0c4b','59fafd4b86f7745ca07e1232','57347ca924597744596b4e71'])

def save(d,f,over=True):
	with io.open(f, 'a' if not over else 'w', encoding='utf8') as the_file:
		the_file.write('%s\n'%(unicode(d)))

def jsb(i):
	return json.dumps(i,indent=4, ensure_ascii=False)#.decode('utf-8')

if __name__ == "__main__":
	api = EFT()
	api.update()
	api.gamestart()
	#api.spawncheck()
	api.setprofile(False)
	api.goshopping()
	#save(jsb(api.locale_en()),'items.json')
	#api.save(jsb(api.locale_en()),'items.json')
	exit(1)