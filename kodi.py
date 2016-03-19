#Author: Jamie Davis <jamiedavis314@gmail.edu>
#Description: Module exposing a python API for Kodi's JSON-RPC web API.
#TODO Pick an API naming convention
#TODO Support identifying the currently-playing selection
#TODO Support listing the CDs by an artist
#TODO Support playing a song by an artist
#TODO Support retrieving album categories
#
#Reference:
# https://kodi.tv/
# http://kodi.wiki/view/JSON-RPC_API/v6
# http://kodi.wiki/view/JSON-RPC_API/Examples
# https://pypi.python.org/pypi/json-rpc/

import requests
import json
import logging

logging.basicConfig(level=logging.DEBUG)

#Provides interface to control the Kodi (audio) media player
#Members:
# audioPlayerID 	integer
# artists 				list of Audio.Details.Artist's
# albums					list of Audio.Details.Album's
# artistToAlbums	maps artist to list of Audio.Details.Album's
# genreToAlbums	  maps genre to list of Audio.Details.Album's
class Kodi:
	PLAYER_PROPERTIES = ['canrotate', 'canrepeat', 'speed', 'canshuffle', 'shuffled', 'canmove', 'subtitleenabled', 'percentage', 'type', 'repeat', 'canseek', 'currentsubtitle', 'subtitles', 'totaltime', 'canzoom', 'currentaudiostream', 'playlistid', 'audiostreams', 'partymode', 'time', 'position', 'canchangespeed']
	BASIC_PAYLOAD = { "jsonrpc": "2.0", "id": 0 }
	MIN_VOLUME = 0
	MAX_VOLUME = 100
	VOLUME_STEP = 10
	
	def __init__ (self, user, password, ip, port=8080):
		self.url = "http://%s:%s@%s:%i/jsonrpc" % (user, password, ip, port)
		self.requestHeaders = {'content-type': 'application/json'}
		self._AssertPingable()
		
		self.audioPlayerID = self._DetermineAudioPlayerID()
		self.artists = self.AudioLibrary_GetArtists()
		self.albums = self.AudioLibrary_GetAlbums()

		#construct artist map using artists
		self.artistToAlbums = {}
		for artist in self.artists:
			albums = [alb for alb in self.albums if alb['artist'][0] == artist['artist']]
			if (albums): #there may not be any, e.g. for multi-artist collections
				self.artistToAlbums[artist['artist']] = albums 
			
		#construct genre map using albums
		self.genreToAlbums = {}		
		for album in self.albums:
			for genre in album['genre']:
				if (genre not in self.genreToAlbums):
					self.genreToAlbums[genre] = []
				self.genreToAlbums[genre].append(album)
				
		for genre in self.genreToAlbums.keys():
			info = ["%s (%s)" % (alb['artist'], alb['label']) for alb in self.genreToAlbums[genre]]
			infoStr = ""
			for i in info:
				infoStr += " " + i
			logging.debug("Kodi::__init__: %s -> %s" % (genre, infoStr))
				
		logging.debug("Kodi::__init__: Found %i albums by %i artists" % (len(self.albums), len(self.artistToAlbums.keys())))
		logging.debug("Kodi::__init__: Found %i albums in %i genres" % (len(self.albums), len(self.genreToAlbums.keys())))
		logging.debug("Kodi::__init__: genres: %s" % (self.genreToAlbums.keys()))		
		logging.debug("Kodi::__init__: url <%s> audioPlayerID <%s>" % (self.url, self.audioPlayerID))
		
	def _AssertPingable (self):
		payload = dict(self.BASIC_PAYLOAD)
		payload['method'] = 'JSONRPC.Ping'
		response = self.__postRequest(payload)
		logging.debug("Kodi::_AssertPingable: response: %s: encoding %s text %s" % (response, response.encoding, response.text))
		rjson = response.json()
		assert(rjson['result'] == 'pong')
				
	#Returns the list of active players as json
	def Player_GetActivePlayers (self):	
		payload = dict(self.BASIC_PAYLOAD)
		payload['method'] = "Player.GetActivePlayers"		
	
		response = self.__postRequest(payload)
		logging.debug("Kodi::Player_GetActivePlayers: response: %s: encoding %s text %s" % (response, response.encoding, response.text))		
		rjson = response.json()
		return rjson
	
	def AudioLibrary_GetArtists (self):
		payload = dict(self.BASIC_PAYLOAD)
		payload['method'] = "AudioLibrary.GetArtists"		
	
		response = self.__postRequest(payload)
		logging.debug("Kodi::AudioLibrary_GetArtists: response: %s: encoding %s text %s" % (response, response.encoding, response.text))		
		rjson = response.json()
		artists = rjson['result']['artists']
		return artists
		
	def AudioLibrary_GetAlbums (self):
		payload = dict(self.BASIC_PAYLOAD)
		payload['method'] = "AudioLibrary.GetAlbums"
		properties = ["playcount", "artist", "genre"]
		payload['params'] = {'properties': properties}
	
		response = self.__postRequest(payload)
		logging.debug("Kodi::AudioLibrary_GetAlbums: response: %s: encoding %s text %s" % (response, response.encoding, response.text))		
		rjson = response.json()
		albums = rjson['result']['albums']
		return albums
	
	#return json describing the requested properties
	#defaults to all possible properties
	def Player_GetProperties (self, properties=PLAYER_PROPERTIES):
		payload = dict(self.BASIC_PAYLOAD)
		payload['method'] = "Player.GetProperties"
		payload['params'] = {'playerid': self.audioPlayerID,
												'properties': properties
												}
				
		response = self.__postRequest(payload)
		logging.debug("Kodi::Player_GetProperties: response: %s: encoding %s text %s" % (response, response.encoding, response.text))		
		rjson = response.json()
		return rjson
			
	#return the ID of the active audio player, or None
	def _DetermineAudioPlayerID (self):
		getActivePlayersJson = self.Player_GetActivePlayers() 
		players = getActivePlayersJson['result']
		audioPlayers = [p for p in players if (p['type'] == 'audio')]
		#at most 1 audio player	
		assert(len(audioPlayers) < 2)
		playerID = None
		if (audioPlayers):
			playerID = audioPlayers[0]['playerid']
		return playerID		
	
	def Player_GetItem (self):
		payload = dict(self.BASIC_PAYLOAD)
		payload['method'] = "Player.GetItem"
		payload['params'] = {"playerid": self.audioPlayerID}
	
		response = self.__postRequest(payload)
		logging.debug("Kodi::Player_GetItem: response: %s: encoding %s text %s" % (response, response.encoding, response.text))		
		rjson = response.json()
		logging.debug("Kodi::Player_GetItem: rjson %s" % (rjson))			
	
	def RaiseVolume (self):
		currVolume = self.Application_GetVolume()
		if (currVolume < self.MAX_VOLUME):
			newVolume = currVolume + self.VOLUME_STEP
			newVolume = min(newVolume, self.MAX_VOLUME)
			self.Application_SetVolume(newVolume)
			logging.debug("Kodi::RaiseVolume: Raised volume from %i to %i" % (currVolume, newVolume))
		else:
			logging.debug("Kodi::RaiseVolume: Volume is already max, nothing to do")
			
	def LowerVolume (self):
		currVolume = self.Application_GetVolume()
		if (self.MIN_VOLUME < currVolume):
			newVolume = currVolume - self.VOLUME_STEP
			newVolume = max(newVolume, self.MIN_VOLUME)
			self.Application_SetVolume(newVolume)
			logging.debug("Kodi::LowerVolume: Lowered volume from %i to %i" % (currVolume, newVolume))
		else:
			logging.debug("Kodi::LowerVolume: Volume is already min, nothing to do")
			
	def Application_SetVolume (self, volume):
		payload = dict(self.BASIC_PAYLOAD)
		payload['method'] = "Application.SetVolume"
		payload['params'] = {"volume": volume}
		
		response = self.__postRequest(payload)
		logging.debug("Kodi::Application_GetVolume: response: %s: encoding %s text %s" % (response, response.encoding, response.text))		
				
	#return the current volume: an integer between MIN_VOLUME and MAX_VOLUME inclusive
	def Application_GetVolume (self):
		payload = dict(self.BASIC_PAYLOAD)
		payload['method'] = "Application.GetProperties"
		payload['params'] = {"properties": ["volume", "muted"]}

		response = self.__postRequest(payload)
		logging.debug("Kodi::Application_GetVolume: response: %s: encoding %s text %s" % (response, response.encoding, response.text))
		rjson = response.json()
		print "rjson %s" % (rjson)
		print "result: %s" % (rjson['result']['volume'])
		currVolume = rjson['result']['volume']
		
		assert(self.MIN_VOLUME <= currVolume and currVolume <= self.MAX_VOLUME) 
		return currVolume
		
	def Audio_IsPlaying (self):
		properties = self.Player_GetProperties(['speed'])
		assert(properties['result'])
		speed = properties['result']['speed']
		return (speed != 0)			
	
	def Player_Pause(self):
		if (self.Audio_IsPlaying()):
			logging.debug("Kodi::Player_Pause: Audio is playing, pausing it")
			self.Player_PlayPause()
		else:
			logging.debug("Kodi::Player_Pause: Audio is not playing, nothing to do")
	
	def Player_Resume(self):
		if (not self.Audio_IsPlaying()):
			logging.debug("Kodi::Player_Resume: Audio is not playing, resuming it")
			self.Player_PlayPause()
		else:
			logging.debug("Kodi::Player_Pause: Audio is already playing, nothing to do")
	
	#toggle play/pause
	def Player_PlayPause (self):	
		payload = dict(self.BASIC_PAYLOAD)
		payload['method'] = "Player.PlayPause"
		payload['params'] = {"playerid": self.audioPlayerID}
		
		response = self.__postRequest(payload)
		logging.debug("Kodi::Player_PlayPause: response: %s: status %i encoding %s text %s" % (response, response.status_code, response.encoding, response.text))
		rjson = response.json()
		logging.debug("Kodi::Player_PlayPause: rjson %s" % (rjson))
		
	#input: payload (kodi json-rpc request)
	#output: response (returned by requests.post)
	#asserts that response status code is OK
	def __postRequest (self, payload):
		logging.debug("Kodi::__postRequest: payload %s" % (payload))
		response = requests.post(self.url, data=json.dumps(payload), headers=self.requestHeaders)
		assert(response.status_code == 200)
		return response
