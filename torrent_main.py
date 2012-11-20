import requests, bencode, hashlib, random

version_number = 1000

file = 'test.torrent'
f = open(file)
data = f.read()
f.close()
data = bencode.bdecode(data)

class File_info:
	'''Takes as input the de-bencoded stream of data
	   Initializes object with organized file information'''
	def __init__(self, data):
		self.announce = data['announce']
		self.creation_date = data.get('creation date', None)
		self.announce_list = data.get('announce-list', None)
		self.comment = data.get('comment', None)
		self.created_by = data.get('created by', None)
		self.encoding = data.get('encoding', None)
		self.info = data['info']
		self.piece_length = data['info']['piece length']
		self.pieces = data['info']['pieces']
		self.private = data['info'].get('private', 0)
		self.name = data['info']['name']
		self.info_hash = hashlib.sha1(bencode.bencode(data['info']))
		try:
			self.length = data['info']['length']
		except KeyError:
			length = 0
			for file in data['info']['files']:
				length += file[length]
			self.length = str(length)

class HTTP:
	def __init__(self):
		self.peer_id = '-PN%s-' %(version_number) + str(random.randint(10**11, 10**12-1))

	def http_request_builder(self):
		parameters = { 'info_hash': file_info.info_hash, 'peer_id': self.peer_id, 'left': file_info.length  }
		request = requests.get(file_info.announce, params = parameters)
		print request.content

file_info = File_info(data)
http_request = HTTP()
print http_request.http_request_builder()
