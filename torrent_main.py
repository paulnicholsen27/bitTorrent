import requests, bencode, hashlib, random, socket, struct
from bitstring import BitArray, BitStream



class DesiredFileInfo:
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
		self.number_of_pieces = len(self.pieces) / 20
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
		self.make_peers()

	def cycle_through_peers(self):
		for p in self.peers:
			p.receive_data()

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

	def make_peers(self):
		'''Opens sockets to viable ip addresses'''
		ip_addresses = self.generate_peer_list()
		self.sockets = []
		for ip in ip_addresses:
			if ip[1]!=0:
				try:
					sock = socket.socket()
					sock.connect(ip)
					self.sockets.append(sock)
				except socket.error:
					print "Caught socket error"
		self.peers = []
		for s in self.sockets:
			self.peers.append(Peer(s))

class Peer:
	def __init__(self, socket):
		self.socket = socket
		self.data = ''
		print self.socket.getpeername()
		self.handshake = self.construct_handshake()
		self.send_handshake()
		self.bitfield = BitArray(file_info.number_of_pieces)
		self.receive_data()

	def __str__(self):
		return 'Peer instance with socket '+str(self.socket)

	def construct_handshake(self):
		pstr = "BitTorrent protocol"
		pstrlen = chr(len(pstr)) #19
		reserved = chr(0) * 8
		return pstrlen + pstr + reserved + file_info.info_hash.digest() + file_info.peer_id

	def send_handshake(self):
		self.socket.send(self.handshake)
		self.peer_handshake = self.socket.recv(68) #!!!TODO - make sure info_hash matches

	def receive_data(self):
		print self, 'is receiving data...'
		self.data += self.socket.recv(2 * 10**6)
		self.parse_data()

	def parse_data(self):
		'''Returns list of tuples consisting of message type and message''' #!!!TODO
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

		while len(self.data) > 0:
			if len(self.data) < 4:
				break
			length = struct.unpack('!I', self.data[:4])[0]
			if length == 0:
				type = 'keep alive'
				self.data = self.data[4:]
			else: #data type anything but 'keep alive'
				type = message_types[ord(self.data[4])]
				length = length-1 #subtract one for message-type byte
				if type == 'bitfield':
					expected_bitfield_length = file_info.number_of_pieces
					print "expected bitfield_length: ", expected_bitfield_length
					self.bitfield = BitArray(bytes=self.data[5:5+length])[:expected_bitfield_length]
				elif type == 'have':
					self.complete_bitfield(struct.unpack('!I', self.data[5:5+length])[0])
				else:
					# type == something else !!!TODO
					pass
				self.data = self.data[5+length:]


	def complete_bitfield(self, have_index):
		self.bitfield[have_index] = 1
		print self.bitfield.bin

	def send_interested(self):
		#send message to peer of length 1 and ID 2
		interested = struct.pack('!I', 1) + struct.pack('!B', 2)
		self.socket.send(self.interested)

	def receive_unchoke(self):
		'''Set status to unchoke if message of length 1 and ID 1 received'''
		if self.socket.recv(10**6) == struct.pack('!I', 1) + struct.pack('!B', 1):
			self.unchoke = True
		else:
			#??? Timeout?  Wait?  Do a little dance?
			pass

	def send_request(self):
		pass

	def structure_pieces(self, messages):
		pass

class OwnedFileInfo:
	def __init__(self):
		self.bitfield = BitArray(file_info.number_of_pieces)



if __name__ == "__main__":
	file_info = DesiredFileInfo('test.torrent')
	my_file = OwnedFileInfo()
	tracker = Tracker(file_info)
	while True:
		print 'going through peers...'
		tracker.cycle_through_peers()
