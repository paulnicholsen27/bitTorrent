import requests, bencode, hashlib, random, socket, struct
from bitstring import BitArray, BitStream



class File_info:
	'''Takes as input the de-bencoded stream of data
	   Initializes object with organized file information'''

	version_number = 1000
	peer_id = '-PN%s-' %(version_number) + str(random.randint(10**11, 10**12-1))

	def __init__(self, file):
		f = open(file)
		data = self.data = bencode.bdecode(f.read()) #??? Why both data and self.data?
		f.close()

		self.announce = self.data['announce']
		self.creation_date = self.data.get('creation date', None)  #!!! Can set arbitrary values as opposed to None for simplicity
		self.announce_list = self.data.get('announce-list', None)
		self.comment = self.data.get('comment', None)
		self.created_by = self.data.get('created by', None)
		self.encoding = self.data.get('encoding', None)
		self.info = self.data['info']
		self.piece_length = self.data['info']['piece length']
		self.pieces = self.data['info']['pieces']
		self.private = self.data['info'].get('private', 0)
		self.name = self.data['info']['name']
		self.info_hash = hashlib.sha1(bencode.bencode(self.data['info']))
		try:
			self.length = self.data['info']['length']
			self.multiple_files = False
		except KeyError:
			length = 0
			for file in self.data['info']['files']:
				length += file[length]
			self.length = str(length)
			self.multiple_files = True




class Tracker:

	def __init__(self, file_info):
		self.file_info = file_info
		self.tracker = self.perform_tracker_request()
		self.peer_ips = self.make_peers(self.generate_peer_list())

	def perform_tracker_request(self):
		'''Requests tracker information'''
		parameters = {'info_hash': self.file_info.info_hash.digest(),
					  'peer_id': self.file_info.peer_id,
					  'left': self.file_info.length,
					  'port':6881}
		request = requests.get(self.file_info.announce, params = parameters)
		tracker = bencode.bdecode(request.content)
		#!!! There are more parameters to possibly be included
		return tracker #!!! Name this better
		#!!!TODO - update tracker to get updated list of peers

	def generate_peer_list(self):
		'''Makes peer list of (ip, port)'''
		peer_list = self.tracker['peers']
		peer_ip_addresses = []
		if type(peer_list) == str:
			for i in range (0, len(peer_list), 6):
				ip = ()
				for char in peer_list[i:i+4]:
					ip += (ord(char),)
				ip_string = "%s.%s.%s.%s" %(ip)
				port = struct.unpack('!H', peer_list[i+4:i+6])[0]
				ip_and_port = (ip_string, port)
				peer_ip_addresses.append(ip_and_port)
		if type(peer_list) == dict:
			pass #!!!todo
		return peer_ip_addresses

	def make_peers(self, ip_addresses):
		'''Opens sockets to viable ip addresses'''
		self.sockets = []
		for ip in ip_addresses:
			if ip[1]!=0:
				try:
					sock = socket.socket()
					sock.connect(ip)
					self.sockets.append(sock)
				except socket.error:
					print "Caught socket error"
					pass
		peers = []
		for s in self.sockets:
			peers.append(Peer(s))



class Peer:
	def __init__(self, socket):
		self.socket = socket
		self.handshake = self.construct_handshake()
		self.send_handshake()
		self.data = self.socket.recv(2 * 10**6) #!!!TODO Change this to a loop; receive_data method
		self.messages = self.parse_data(self.data)
		if self.bitfield_exists == True:
			self.messages = self.complete_bitfield(self.messages)

	def construct_handshake(self):
		pstr = "BitTorrent protocol"
		pstrlen = chr(len(pstr)) #19
		reserved = chr(0) * 8
		return pstrlen + pstr + reserved + file_info.info_hash.digest() + file_info.peer_id

	def send_handshake(self):
		self.socket.send(self.handshake)
		self.peer_handshake = self.socket.recv(68) #!!!TODO - make sure info_hash matches

	def parse_data(self, data):
		'''Returns list of tuples consisting of message type and message'''
		parsed_data = {}
		message_types = {	0 : 'choke',
							1 : 'unchoke',
							2 : 'interested',
							3 : 'not interested',
							4 : 'have',
							5 : 'bitfield',
							6 : 'request',
							7 : 'piece',
							8 : 'cancel'
							 }
		messages = {}
		while len(data) > 0:
			while len(data) < 4:
				data += get_data(self.socket)
			length = struct.unpack('!I', data[:4])[0]
			if length == 0:
				type = 'keep alive'
# 				try: #??? Is any of this necessary?
# 					messages[type] += [data[:4]]
# 				except KeyError:
# 					messages[type] = [data[:4]]
				data = data[4:]
			else:
				id = ord(data[4])
				length = length-1 #subtract one for message-type byte
				type = message_types[id]
				if type == 'bitfield':
					expected_bitfield_length = len(file_info.pieces) / 20
					print "expected bitfield_length: ", expected_bitfield_length
					self.bitfield_exists = True
					bitfield_data = ""
# 					print "raw bitfield: ", data[5:5+length]
					for character in data[5:5+length]:
# 						print "character: ", ord(character)
						bitfield_data += str(bin(ord(character)))[2:]
# 					print "orded bitfield: ", bitfield_data
					bitfield_data = BitArray(bin=bitfield_data)[:expected_bitfield_length]
					print "Lengths: ", expected_bitfield_length, len(bitfield_data)
	# 				print "Binary bitfield: ", bitfield_data
# 					print "length of bitfield: ", len(bitfield_data)
					messages[type] = bitfield_data
				else:
					parsed_data = ""
					for character in data[5:5+length]:
						parsed_data += str(ord(character))#[2:]
					parsed_data = int(parsed_data)
					try:
						messages[type] += [parsed_data]
					except KeyError:
						messages[type] = [parsed_data]
				data = data[5+length:]

 		print "Finished parsing: ", messages
		return messages

	def complete_bitfield(self, messages):
		print "Before alteration: ", messages['bitfield'].bin
		for piece in messages['have']:
# 			print "bitfield: ", messages['bitfield'].bin
			messages['bitfield'][piece] = 1
		print messages['bitfield'].bin
		return messages

	def structure_pieces(self, messages):
		pass




if __name__ == "__main__":
	file_info = File_info('test.torrent')
	tracker = Tracker(file_info)
