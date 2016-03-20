#Author: Jamie Davis <jamiedavis314@gmail.edu>
#Description: Module exposing a python API for Kodi's JSON-RPC web API.
#TODO Pick an API naming convention
#TODO Support identifying the currently-playing selection
#TODO Support listing the CDs by an artist
#TODO Support playing a song by an artist
#TODO Support retrieving album categories
#TODO Update kodi wiki with sample playlist files. Also, why can I see the playlists in Yatse but not through Playlist.GetPlaylists?
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
	APPLICATION_PROPERTIES = ['volume', 'muted', 'name', 'version']
	BASIC_PAYLOAD = { "jsonrpc": "2.0", "id": 0 }
	
	MIN_VOLUME = 0
	MAX_VOLUME = 100	
	VOLUME_STEP = 10
	MUTED = -1
	
	def __init__ (self, user, password, ip, port=8080):
		self.url = "http://%s:%s@%s:%i/jsonrpc" % (user, password, ip, port)
		self.requestHeaders = {'content-type': 'application/json'}
		self._AssertPingable()
		
		self.JSONRPC_Introspect()
		self.audioPlayerID = self._DetermineAudioPlayerID()
				
		self.Playlist_Clear(0)
		self.Playlist_Add(0, 'abc')
		playlists = self.Playlist_GetPlaylists()
		playlistIDs = [p['playlistid'] for p in playlists]
		for p in playlistIDs:
			self.Playlist_GetItems(p)
		
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
	
	##High level functionality
	
	def RaiseVolume (self):
		currVolume = self._GetVolume()
		if (currVolume < self.MAX_VOLUME):
			newVolume = currVolume + self.VOLUME_STEP
			newVolume = min(newVolume, self.MAX_VOLUME)
			self.Application_SetVolume(newVolume)
			logging.debug("Kodi::RaiseVolume: Raised volume from %i to %i" % (currVolume, newVolume))
		else:
			logging.debug("Kodi::RaiseVolume: Volume is already max, nothing to do")
			
	def LowerVolume (self):
		currVolume = self._GetVolume()
		if (self.MIN_VOLUME < currVolume):
			newVolume = currVolume - self.VOLUME_STEP
			newVolume = max(newVolume, self.MIN_VOLUME)
			self.Application_SetVolume(newVolume)
			logging.debug("Kodi::LowerVolume: Lowered volume from %i to %i" % (currVolume, newVolume))
		else:
			logging.debug("Kodi::LowerVolume: Volume is already min, nothing to do")
	
	def PauseMusic(self):
		if (self._IsAudioPlaying()):
			logging.debug("Kodi::PauseMusic: Audio is playing, pausing it")
			self.Player_PlayPause()
		else:
			logging.debug("Kodi::PauseMusic: Audio is not playing, nothing to do")
	
	def ResumeMusic(self):
		if (not self._IsAudioPlaying()):
			logging.debug("Kodi::ResumeMusic: Audio is not playing, resuming it")
			self.Player_PlayPause()
		else:
			logging.debug("Kodi::ResumeMusic: Audio is already playing, nothing to do")
		
	#High-level helpers
		
	def _AssertPingable (self):
		assert(self.JSONRPC_Ping() == 'pong')
		
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
	
	def _IsAudioPlaying (self):
		properties = self.Player_GetProperties(['speed'])		
		speed = properties['speed']
		return (0 < speed)			
	
	#return the current volume: an integer between MIN_VOLUME and MAX_VOLUME inclusive, or self.MUTED
	def _GetVolume (self):
		result = self.Application_GetProperties(["volume", "muted"])
		
		assert('volume' in result.keys())
		assert('muted' in result.keys())
		volume = result['volume']
		muted = result['muted']
						
		assert(self.MIN_VOLUME <= volume and volume <= self.MAX_VOLUME)		
		if (muted): 
			return self.MUTED
		else:
			return volume	
					
	##Kodi JSON-RPC APIs
	#These APIs are named X_Y and invoke the associated X.Y API described in http://kodi.wiki/view/JSON-RPC_API/v6
	#TODO Each returns the response.json()['result'].
	#			Refer to the documentation associated with each API to see the format of the response.
		
	#JSONRPC
	
	def JSONRPC_Ping (self):
		payload = dict(self.BASIC_PAYLOAD)
		payload['method'] = 'JSONRPC.Ping'
		response = self.__postRequest(payload)
		rjson = response.json()
		return rjson['result']
		
	def JSONRPC_Introspect (self):
		payload = dict(self.BASIC_PAYLOAD)
		payload['method'] = "JSONRPC.Introspect"
		response = self.__postRequest(payload)
		rjson = response.json()
		return rjson['result']
		
	#Playlist
		
	def Playlist_Add (self, playlistID, item):
		payload = dict(self.BASIC_PAYLOAD)
		payload['method'] = "Playlist.Add"
		#TODO testing
		payload['params'] = {'playlistid': playlistID,
												'item': {'songid': 1981}
												}
	
		response = self.__postRequest(payload)
		rjson = response.json()
		return rjson['result']	
	
	def Playlist_Clear (self, playlistID):
		payload = dict(self.BASIC_PAYLOAD)
		payload['method'] = "Playlist.Clear"
		payload['params'] = {'playlistid': playlistID}		
	
		response = self.__postRequest(payload)
		rjson = response.json()
		return rjson['result']	
	
	#returns a dict; keys are as follows:
	#'items' is a list of dicts with keys 'id', 'label', 'type'
	#'limits' is a dict with keys end, start, total
	def Playlist_GetItems (self, playlistID):
		payload = dict(self.BASIC_PAYLOAD)
		payload['method'] = "Playlist.GetItems"
		payload['params'] = {'playlistid': playlistID}		
	
		response = self.__postRequest(payload)
		rjson = response.json()
		return rjson['result']	
	
	def Playlist_GetPlaylists (self):
		payload = dict(self.BASIC_PAYLOAD)
		payload['method'] = "Playlist.GetPlaylists"		
	
		response = self.__postRequest(payload)
		rjson = response.json()
		return rjson['result']
	
	#Player	
			
	#Returns the list of active players as json
	def Player_GetActivePlayers (self):	
		payload = dict(self.BASIC_PAYLOAD)
		payload['method'] = "Player.GetActivePlayers"		
	
		response = self.__postRequest(payload)
		rjson = response.json()
		return rjson
				
	def Player_GetItem (self):
		payload = dict(self.BASIC_PAYLOAD)
		payload['method'] = "Player.GetItem"
		payload['params'] = {"playerid": self.audioPlayerID}
	
		response = self.__postRequest(payload)
		rjson = response.json()
		logging.debug("Kodi::Player_GetItem: rjson %s" % (rjson))
		
	#return json describing the requested properties
	#defaults to all possible properties
	def Player_GetProperties (self, properties=PLAYER_PROPERTIES):
		payload = dict(self.BASIC_PAYLOAD)
		payload['method'] = "Player.GetProperties"
		payload['params'] = {'playerid': self.audioPlayerID,
												'properties': properties
												}
				
		response = self.__postRequest(payload)
		rjson = response.json()
		return rjson['result']
				
	#toggle play/pause
	def Player_PlayPause (self):	
		payload = dict(self.BASIC_PAYLOAD)
		payload['method'] = "Player.PlayPause"
		payload['params'] = {"playerid": self.audioPlayerID}
		
		response = self.__postRequest(payload)
		rjson = response.json()
		logging.debug("Kodi::Player_PlayPause: rjson %s" % (rjson))
	
	#AudioLibrary
	
	def AudioLibrary_GetAlbums (self):
		payload = dict(self.BASIC_PAYLOAD)
		payload['method'] = "AudioLibrary.GetAlbums"
		properties = ["playcount", "artist", "genre"]
		payload['params'] = {'properties': properties}
	
		response = self.__postRequest(payload)
		rjson = response.json()
		albums = rjson['result']['albums']
		return albums
	
	def AudioLibrary_GetArtists (self):
		payload = dict(self.BASIC_PAYLOAD)
		payload['method'] = "AudioLibrary.GetArtists"		
	
		response = self.__postRequest(payload)
		rjson = response.json()
		artists = rjson['result']['artists']
		return artists			
			
	#Application
	
	def Application_SetVolume (self, volume):
		payload = dict(self.BASIC_PAYLOAD)
		payload['method'] = "Application.SetVolume"
		payload['params'] = {"volume": volume}
		
		response = self.__postRequest(payload)
		return response['json']		
	
	def Application_GetProperties (self, properties=APPLICATION_PROPERTIES):		
		for p in properties:
			assert(p in self.APPLICATION_PROPERTIES)
		
		payload = dict(self.BASIC_PAYLOAD)
		payload['method'] = "Application.GetProperties"
		payload['params'] = {"properties": properties}
		response = self.__postRequest(payload)		
		rjson = response.json()
		return rjson['result']
		
	#input: payload (kodi json-rpc request)
	#output: response (returned by requests.post)
	#asserts that response status code is OK
	def __postRequest (self, payload):
		logging.debug("Kodi::__postRequest: payload %s" % (payload))
		response = requests.post(self.url, data=json.dumps(payload), headers=self.requestHeaders)		
		logging.debug("Kodi::__postRequest: response: %s: encoding %s text %s" % (response, response.encoding, response.text))
		assert(response.status_code == 200)
		return response