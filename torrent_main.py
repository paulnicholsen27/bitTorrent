import random, socket, struct, datetime, hashlib, sys
import requests
import bencode
from bitstring import BitArray, BitStream




class DesiredFileInfo(object):
	'''Takes as input the torrent file
	   Initializes object with organized file information'''


	def __init__(self, torrent_file):
		decoded_data = bencode.bdecode(open(torrent_file).read())

		# Basic parameters
		self.announce = decoded_data['announce']
		self.creation_date = decoded_data.get('creation date', None)  #!!! Can set arbitrary values as opposed to None for simplicity
		self.announce_list = decoded_data.get('announce-list', None)
		self.comment = decoded_data.get('comment', None)
		self.created_by = decoded_data.get('created by', None)
		self.encoding = decoded_data.get('encoding', None)
		self.private = decoded_data['info'].get('private', 0)
		self.file_name = decoded_data['info']['name']
		self.info_hash = hashlib.sha1(bencode.bencode(decoded_data['info']))

		# How many files
		multiple_files = decoded_data.get('files', None)
		self.num_files = len(multiple_files) if multiple_files else 1
		print "How many files? ", self.num_files

		# Total length (in bytes)
		try:
			self.length = decoded_data['info']['length']
		except KeyError:
			self.length = sum(eachfile['length'] for eachfile in decoded_data['info']['files'])

		# Pieces
		self.pieces = decoded_data['info']['pieces']
		self.piece_length = decoded_data['info']['piece length']
		assert len(self.pieces) % 20 == 0
		self.number_of_pieces = len(self.pieces) / 20
		# Each entry in pieces is a 20-byte byte string, so dividing by 20 gives the number of pieces
		
		# Blocks
		self.block_length = max(2**14, self.piece_length)
		self.whole_blocks_per_piece = self.piece_length / self.block_length
		self.last_block_size = self.piece_length % self.block_length # will often be zero


class Client(object):

	version_number = 1000
	my_peer_id = '-PN%s-' %(version_number) + str(random.randint(10**11, 10**12-1))

	def __init__(self, file_out):
		self.file_out = open(file_out, 'wb')
		self.bitfield = BitArray(file_info.number_of_pieces)
		self.peer_connections = [] # created later

	def perform_tracker_request(self, file_info):
		'''Requests tracker information'''
		parameters = {'info_hash': file_info.info_hash.digest(),
					  'peer_id': my_peer_id,
					  'left': file_info.length,
					  'port':6881}
		request = requests.get(file_info.announce, params = parameters)
		tracker_data = bencode.bdecode(request.content)
		#!!! There are more parameters to possibly be included
		return tracker_data
		#!!!TODO - update tracker to get updated list of peers

	def generate_peer_ip_list(self, tracker_data):
		'''Makes peer list of (ip, port)'''
		peer_list = tracker_data['peers']
		print "Length of peer_list: ", len(peer_list)
		peer_ip_addresses = []
		if type(peer_list) == str:
			for i in range (0, len(peer_list), 6):
				print "Peer attempt starting at point", i
				ip = ()
				for char in peer_list[i:i+4]:
					ip += (ord(char),)
				ip_string = "%s.%s.%s.%s" %(ip)
				port = struct.unpack('!H', peer_list[i+4:i+6])[0]
				ip_and_port = (ip_string, port)
				print ip_and_port
				peer_ip_addresses.append(ip_and_port)
		if type(peer_list) == list:
			for peer_dictionary in peer_list:
				ip_and_port = (peer_dictionary['ip'], peer_dictionary['port'])
				peer_ip_addresses.append(ip_and_port)
		return peer_ip_addresses

	def connect_to_peer(self, ip, port):
		try:
			sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			sock.connect((ip, port))
			new_peer = PeerConnection(sock)	
			return new_peer	
		except socket.error as e:
			print "Caught socket error:", e, "on socket", sock.fileno(), "from peer IP", ip

	def make_peers(self, ip_addresses, handshake, interested):
		'''Returns list of PeerConnection objects, tied to open sockets to viable ip addresses'''
		for ip, port in ip_addresses:
			if ip != 0:
				if self.connect_to_peer(ip, port):
					self.peer_connections.append(new_peer)
					#piece_data = new_peer.get_data(self.bitfield, self.file_info.block_length, self.file_info.last_block_size) #todo: move this from here

	def update_bitfield(self, index):
		'''Updates bitfield info for downloaded pieces'''
		self.bitfield[index] = 1
		print "Current Bitfield: ", self.bitfield.bin

	def cycle_through_peers(self):
		for p in self.peers:
			p.receive_data()

	def write_piece_to_file(self, start_location, piece_data):
		self.file_out.seek(start_location)
		self.file_out.write(piece_data[13:])

	def make_handshake(self, info_hash):
		pstr = "BitTorrent protocol"
		pstrlen = chr(len(pstr)) #19
		reserved = chr(0) * 8
		handshake =  pstrlen + pstr + reserved + info_hash.digest() + self.my_peer_id
		return handshake

	def make_interested(self):
		'''send message to peer of length 1 and ID 2'''
		return struct.pack('!I', 1) + struct.pack('!B', 2) 


class PeerConnection(object):
	def __init__(self, socket, handshake, interested):
		self.socket = socket
		self.data = ''
		self.bitfield = BitArray(file_info.number_of_pieces) #Initially set to all zeroes unless replaced with peer bitfield or updated with 'have' messages
		
		self.sock.send(handshake)
		handshake_hopefully = self.socket.recv(68)
		# Todo: check that handshake back takes correct form
		# self.receive_data() This should definitely not be happening on init.
		self.sock.send(interested)
		self.data += self.sock.recv(10**6)
		self.parse_data() # we're going to move this in a second
		print "Made peer"

	def __str__(self):
		return 'Peer instance with socket ' + str(self.socket.fileno())

	def receive_data(self):
		print self, 'is receiving data...'
		self.data += self.socket.recv(2 * 10**6)
		self.parse_data()

	def parse_data(self):
		'''Parses data and handles different message_types accordingly'''
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
				msg_type = 'keep alive'
				self.data = self.data[4:]
			else: #data type anything but 'keep alive'
				try:
					print "Trying to parse data"
					msg_type = message_types[ord(self.data[4])]
				except KeyError:
					self.receive_data()
				length = length-1 #subtract one for message-type byte
				if msg_type == 'choke':
					pass
				elif msg_type == 'unchoke':
					self.unchoke = True
					print "Unchoked"
				elif msg_type == 'interested':
					pass
				elif msg_type == 'not interested':
					pass
				elif msg_type == 'have':
					self.complete_bitfield(struct.unpack('!I', self.data[5:5+length])[0])
				elif msg_type == 'bitfield':
					expected_bitfield_length = file_info.number_of_pieces
					print "expected bitfield_length: ", expected_bitfield_length
					self.bitfield = BitArray(bytes=self.data[5:5+length])[:expected_bitfield_length]
				elif msg_type == 'request':
					pass
				elif msg_type == 'piece':
					pass
				elif msg_type == 'cancel':
					pass
				else:
					break
				self.data = self.data[5+length:]


	def complete_bitfield(self, have_index):
		self.bitfield[have_index] = 1
	#	print self.bitfield.bin

	def get_data(self, tracker_bitfield, block_length, last_block_size):
		for piece_num in range(len(tracker_bitfield)):
			if not tracker_bitfield[piece_num]:
				print "sending request", piece_num
				piece_data = self.returns_a_piece(tracker_bitfield, piece_num, block_length, last_block_size)
				self.write_piece_to_file(piece_data, piece_num)
				self.update_bitfield(self.index)


	def returns_a_piece(self, tracker_bitfield, piece_num, block_length, last_block_size):
		'''Constructs and sends a request for one piece that peer has and user does not'''
		print "Sending request", piece_num
		if self.bitfield[piece_num]:
			print "Found a piece I don't have"
			piece_data = ''
			#peer has piece downloader does not

			for block_num in range(file_info.whole_blocks_per_piece):
				block = self.get_block(piece_num, block_num, block_length)
				piece_data += block
			if last_block_size:
				block = self.get_block(piece_num, block_num, last_block_size)
				piece_data += block
			return piece_data

	def get_block(self, piece_num, block_num, block_length):
		print "requesting a block"
		block_data = ''
		request_msg = self.make_request_msg(13, 6, piece_num, block_num*block_length, block_length)
		self.sock.send(request_msg)
		while len(block_data) < block_length + 13: #todo: learn why 13
			block_data += self.sock.recv(2**15)
		return block_data

	def make_request_msg(self, thirteen, six, piece_num, start_point, block_length):
		request_message = (struct.pack('!I', thirteen) + struct.pack('!B', six) +
						  struct.pack('!I', piece_num) +
						  struct.pack('!I', start_point) +
			  			  struct.pack('!I', block_length))
		#TODO: learn what thirteen and six are
		return request_message

	def check_piece(self, file):
		return hashlib.sha1(self.current_piece[13:]).digest() == file_info.pieces[20*self.index:20*(self.index+1)]



	def send_cancel(self):
		cancel = (struct.pack('!I', 13) + struct.pack('!B', 8) +
			      struct.pack('!I', self.index) +
			      struct.pack('!I', self.begin) +
			      struct.pack('!I', self.length))
		self.sock.send(cancel)


def setup_client(filename):
	file_info = DesiredFileInfo(filename)
	client = Client(file_info.file_name)
	tracker_data = client.perform_tracker_request(file_info)
	handshake = client.make_handshake(file_info.info_hash)
	interested = client.make_interested()
	peer_ips = client.generate_peer_ip_list(tracker_data)
	client.peer_connections = client.make_peers(peer_ips, handshake, interested)

	return client


if __name__ == "__main__":
	torrent_file = sys.argv[1] if len(sys.argv) > 1 else 'test.torrent'
	client = setup_client(torrent_file)

	while any(client.bitfield)==False:
		print 'going through peers...'
		peers = client.make_peers()
		client.cycle_through_peers()
	print "File completed"
