import random, socket, struct, datetime, hashlib
import requests
import bencode
from bitstring import BitArray, BitStream




class DesiredFileInfo(object):
	'''Takes as input the de-bencoded stream of data
	   Initializes object with organized file information'''

	version_number = 1000
	peer_id = '-PN%s-' %(version_number) + str(random.randint(10**11, 10**12-1))

	def __init__(self, file):
		f = open(file)
		self.data = bencode.bdecode(f.read())
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
			self.length = 0
			for file in self.data['info']['files']:
				self.length += file['length']
			self.multiple_files = True
		print "Multiple files? ", self.multiple_files
		self.number_of_whole_blocks_in_whole_piece = 1
		self.last_block_size = 0
		self.block_length = 2**14
		if self.piece_length > 2**14:
			'''Pieces are too large to download as whole chunks'''
			print "Will use blocks"
			self.number_of_whole_blocks_in_whole_piece = self.piece_length / self.block_length
			if self.piece_length % self.block_length != 0:
				print "Final last block is smaller"
				self.last_block_size = self.piece_length % self.block_length
		else:
			print "Only one block/piece"
			self.number_of_whole_blocks_in_whole_piece = 1
			self.block_length = self.piece_length

		if self.length % self.piece_length != 0: #handles final, probably smaller,
			self.last_piece_size = self.length % self.piece_length
			self.number_of_whole_pieces = self.number_of_pieces - 1
		else:
			self.number_of_whole_pieces = self.number_of_pieces


class Tracker(object):

	def __init__(self, file_info):
		self.file_info = file_info
		self.my_file = OwnedFileInfo()
		print self.my_file

		self.peers = self.make_peers()


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
		tracker_data = bencode.bdecode(request.content)
		#!!! There are more parameters to possibly be included
		return tracker_data
		#!!!TODO - update tracker to get updated list of peers

	def generate_peer_list(self):
		'''Makes peer list of (ip, port)'''
		self.tracker_data = self.perform_tracker_request()
		peer_list = self.tracker_data['peers']
		print "Length of peer_list: ", len(peer_list)
		peer_ip_addresses = []
		if type(peer_list) == str:
			for i in range (0, len(peer_list), 6):
				print "Peer attempt #", i
				ip = ()
				for char in peer_list[i:i+4]:
					ip += (ord(char),)
				ip_string = "%s.%s.%s.%s" %(ip)
				port = struct.unpack('!H', peer_list[i+4:i+6])[0]
				ip_and_port = (ip_string, port)
				peer_ip_addresses.append(ip_and_port)
		if type(peer_list) == list:
			for peer_dictionary in peer_list:
				ip_and_port = (peer_dictionary['ip'], peer_dictionary['port'])
				peer_ip_addresses.append(ip_and_port)
		return peer_ip_addresses

	def make_peers(self):
		'''Returns list of Peer objects, tied to open sockets to viable ip addresses'''
		ip_addresses = self.generate_peer_list()
		self.sockets = []
		for ip in ip_addresses:
			if ip[1]!=0:
				try:
					sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
					sock.connect(ip)
					self.sockets.append(sock)
					print "Socket made"
				except socket.error:
					print "Caught socket error"
		peer_list = []
		print "Peer list: ", peer_list
		for s in self.sockets:
			try:
				peer_list.append(Peer(s, self.my_file))
			except socket.error:
				print "Failed to make peer`"
		print "Number of peers: ", len(peer_list)
 		return peer_list

class Peer(object):
	def __init__(self, socket,file):
		self.socket = socket
		self.data = ''
		self.send_handshake()
		self.bitfield = BitArray(file_info.number_of_pieces) #Initially set to all zeroes unless replaced with peer bitfield or updated with 'have' messages
		self.receive_data()
		self.send_interested()
		self.send_request(file)
		print "Made peer"

	def __str__(self):
		return 'Peer instance with socket ' + str(self.socket)

	def send_handshake(self):
		pstr = "BitTorrent protocol"
		pstrlen = chr(len(pstr)) #19
		reserved = chr(0) * 8
		handshake =  pstrlen + pstr + reserved + file_info.info_hash.digest() + file_info.peer_id
		self.socket.send(handshake)
		self.peer_handshake = self.socket.recv(68) #!!!TODO - make sure info_hash matches

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
				type = 'keep alive'
				self.data = self.data[4:]
			else: #data type anything but 'keep alive'
				try:
					print "Trying to parse data"
					type = message_types[ord(self.data[4])]
				except KeyError:
					self.receive_data()
				length = length-1 #subtract one for message-type byte
				if type == 'choke':
					pass
				elif type == 'unchoke':
					self.unchoke = True
					print "Unchoked"
				elif type == 'interested':
					pass
				elif type == 'not interested':
					pass
				elif type == 'have':
					self.complete_bitfield(struct.unpack('!I', self.data[5:5+length])[0])
				elif type == 'bitfield':
					expected_bitfield_length = file_info.number_of_pieces
					print "expected bitfield_length: ", expected_bitfield_length
					self.bitfield = BitArray(bytes=self.data[5:5+length])[:expected_bitfield_length]
				elif type == 'request':
					pass
				elif type == 'piece':
					pass
				elif type == 'cancel':
					pass
				else:
					break
				self.data = self.data[5+length:]


	def complete_bitfield(self, have_index):
		self.bitfield[have_index] = 1
	#	print self.bitfield.bin

	def send_interested(self):
		'''send message to peer of length 1 and ID 2'''
		interested = struct.pack('!I', 1) + struct.pack('!B', 2)
		self.socket.send(interested)
		print "Interested"
		self.data += self.socket.recv(10**6)
		self.parse_data()

	def send_request(self, file):
		'''Constructs and sends a request for piece that peer has and user does not'''
		for i in range(len(file.bitfield)):
			print "Sending request"
			self.current_piece = ""
			if file.bitfield[i] == 0 and self.bitfield[i] == 1:
				print "Found a piece I don't have"
				#peer has piece downloader does not
				self.index = i
				self.length = file_info.block_length
				self.begin = 0
				for j in range(file_info.number_of_whole_blocks_in_whole_piece):
					print "Sending a request message"
					request_message = (struct.pack('!I', 13) + struct.pack('!B', 6) +
									  struct.pack('!I', self.index) +
									  struct.pack('!I',self.begin) +
						  			  struct.pack('!I', self.length))
					self.socket.send(request_message)
					self.receive_block()
					self.begin += self.length
					print "New data received"
					self.piece_check(file)
#				print "Current Piece: ", self.current_piece, "\n"
#				print "Current Piece Repr: ", repr(self.current_piece[13:])
				if file_info.last_block_size != 0:
					self.length = file_info.last_block_size
					request_message = (struct.pack('!I', 13) + struct.pack('!B', 6) +
									  struct.pack('!I', self.index) +
									  struct.pack('!I', self.begin) +
						  			  struct.pack('!I', self.length))
					self.socket.send(request_message)
					self.receive_block()
					print "End of piece received"
					self.piece_check(file)

	def piece_check(self, file):
		if True: #hashlib.sha1(self.current_piece[13:]).digest() == file_info.pieces[20*self.index:20*(self.index+1)]:
			print "Yay, a new piece!"
			self.write_to_file(file)
			file.update_bitfield(file, self.index)
		else:
			print "Current Piece: ", repr(hashlib.sha1(self.current_piece[13:]).digest())
			print "Expected: ", repr(file_info.pieces[20*self.index:20*(self.index+1)])
			print "Doesn't match, reset"
			self.current_piece = ""

	def receive_block(self):
		'''peer will respond with a piece message'''
		print "Receiving data"
 		new_data = self.socket.recv(2**15)
 		self.current_piece += new_data
 		if len(self.current_piece) < self.length + 13:
 			self.receive_block()
 			print "Need more data"
 		#print "Piece so far: ", self.current_piece
 		print "Data Received"


	def write_to_file(self, file):
		file.f.seek(self.index * file_info.piece_length)
		file.f.write(self.current_piece[13:])

	def send_cancel(self):
		cancel = (struct.pack('!I', 13) + struct.pack('!B', 8) +
			      struct.pack('!I', self.index) +
			      struct.pack('!I', self.begin) +
			      struct.pack('!I', self.length))
		self.socket.send(cancel)

class OwnedFileInfo(object):
	def __init__(self):
		self.bitfield = BitArray(file_info.number_of_pieces)
		self.file_creator()

	def file_creator(self):
		self.f = open(file_info.name, 'wb')
		print "Filename is: ", self.f.name

	def update_bitfield(self, file, index):
		'''Updates bitfield info for downloaded pieces'''
		self.bitfield[index] = 1
		print "Current Bitfield: ", file.bitfield.bin


if __name__ == "__main__":
	file_info = DesiredFileInfo('test.torrent')
	tracker = Tracker(file_info)
	tracker.perform_tracker_request()


	while any(tracker.my_file.bitfield)==False:
		print 'going through peers...'
  		peers = tracker.make_peers()
		tracker.cycle_through_peers()
	print "File completed"
