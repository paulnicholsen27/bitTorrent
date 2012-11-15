import re
from bencode2 import bdecode2, _dechunk #for testing purposes

#I realize this exists but I thought it would be a good exercise in recursion

def decoder(data):
	splits = list(data)
	splits.reverse()
	decoded = split_translator(splits)
	return decoded


def split_translator(splits):
	numbers = re.compile('\d+')
	current_character = splits.pop()
	if len(splits) == 0:
		return splits

	if current_character == 'd': #sequence is a dictionary
		dict_item = {}
		current_character = splits.pop()
		while current_character != 'e':
			splits.append(current_character)
			key = split_translator(splits)
			dict_item[key] = split_translator(splits)
			current_character = splits.pop()
		return dict_item

	elif numbers.match(current_character): #sequence is a string
		word_length = current_character
		next_character = splits.pop()
		while next_character != ':':
			word_length += next_character
			next_character = splits.pop()
		word_length = int(word_length)
		string = ''
		i = 0
		while i < word_length:
			current_character = splits.pop()
			string += current_character
			i += 1
		return string

	elif current_character == 'l':#sequence is a list
		list_item = []
		current_character = splits.pop()
		while current_character != 'e':
			splits.append(current_character)
			list_item.append(split_translator(splits))
			current_character = splits.pop()
		return list_item

	elif current_character == 'i':#sequence is an integer
		integer = ''
		current_character = splits.pop()
		while current_character != 'e':
			integer += current_character
			current_character = splits.pop()
		return int(integer)
	else:
		print "Error of some sort", current_character, 100

f = open("blender_foundation_-_big_buck_bunny_720p.torrent")
data3 = f.read()

# list_test = 'lli12e3:abcee'
# data_dic_and_str_and_int = 'd5:apple3:red5:grape6:purplei3e5:house2:abi89ee'
# data_dic_and_str ='12:abcdefghijkl'
data2 = 'd5:applel3:redi4el4:good3:badee6:bananal6:yellowli2e9:potassiumedi7ei3eeee'
print "Me : ", decoder(data2)
print "Him: ", bdecode2(data2)
print decoder(data3) == bdecode2(data3)
